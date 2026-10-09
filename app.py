import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# LLAVE DE SEGURIDAD INDISPENSABLE PARA LLENAR VARIABLES DE SESIÓN EN CELULARES
app.secret_key = 'minga_control_alistamiento_key_secreta_2026'

# Configuración de la Base de Datos SQLite Local
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'minga.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------------------------------------------------
# MODELOS DE LA BASE DE DATOS
# -------------------------------------------------------------

# 1. Tabla de Usuarios (Para los operadores creados desde la web)
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), default='operador') # 'administrador' o 'operador'

# 2. Tabla de Información de Móviles (Reemplazo definitivo del Excel)
class InformacionMovil(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehiculo = db.Column(db.String(50), unique=True, nullable=False) # Número de móvil o Placa
    ruta = db.Column(db.String(50), nullable=False)
    tabla = db.Column(db.String(50), nullable=False)
    hora = db.Column(db.String(50), nullable=False)
    novedad = db.Column(db.String(255), default='SIN NOVEDAD')

# 3. Tabla de Registros de Procesos Diarios
class RegistroVehicular(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehiculo = db.Column(db.String(50), nullable=False)
    proceso = db.Column(db.String(100), nullable=False)
    fecha_hora = db.Column(db.String(100), nullable=False)
    observacion = db.Column(db.String(255), nullable=True)

# -------------------------------------------------------------
# CONTROL DE RUTAS DE AUTENTICACIÓN (LOGIN / LOGOUT)
# -------------------------------------------------------------
@app.route('/', methods=['GET'])
def index():
    if session.get('rol') == 'administrador':
        return redirect(url_for('admin_panel'))
    elif session.get('rol') == 'operador':
        return redirect(url_for('operador'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_input = request.form.get('usuario', '').strip().lower()
        contrasena_input = request.form.get('contrasena', '').strip()
        
        # 1. ACCESO FIJO PARA EL ADMINISTRADOR (Blindado contra borrados del servidor)
        if usuario_input == 'administrador' and contrasena_input == 'admin1234':
            session.clear()
            session['nombre'] = 'Administrador General'
            session['rol'] = 'administrador'
            return redirect(url_for('admin_panel'))
            
        # 2. ACCESO PARA LOS OPERADORES CREADOS EN LA BASE DE DATOS
        user = Usuario.query.filter_by(username=usuario_input).first()
        
        if user and check_password_hash(user.password_hash, contrasena_input):
            session.clear()
            session['user_id'] = user.id
            session['nombre'] = user.nombre
            session['rol'] = user.rol
            
            if user.rol == 'administrador':
                return redirect(url_for('admin_panel'))
            return redirect(url_for('operador'))
        else:
            flash("Usuario o contraseña incorrectos", "error")
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------------------------------------------------
# PANEL DEL OPERADOR (VISTA Y GUARDADO COMPATIBLE CON CELULARES)
# -------------------------------------------------------------
@app.route('/operador', methods=['GET', 'POST'])
def operador():
    if session.get('rol') != 'operador':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        vehiculo = request.form.get('vehiculo')
        proceso = request.form.get('proceso')
        observacion = request.form.get('observacion', 'Ninguna novedad')
        
        # Estampa horaria para la base de datos
        ahora = datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')
        
        nuevo_registro = RegistroVehicular(
            vehiculo=vehiculo,
            proceso=proceso,
            fecha_hora=ahora,
            observacion=observacion
        )
        db.session.add(nuevo_registro)
        db.session.commit()
        
        # RETORNO ASÍNCRONO: Evita que el navegador de WhatsApp congele la pantalla al guardar
        return jsonify({"status": "success", "message": "Registro guardado correctamente"})

    procesos_lista = ["Inspección", "Lavado", "Mantenimiento", "Alistamiento Final"]
    ultimos_registros = RegistroVehicular.query.order_by(RegistroVehicular.id.desc()).limit(50).all()
    return render_template('operador.html', procesos=procesos_lista, registros=ultimos_registros)

# BUSCADOR DINÁMICO QUE REEMPLAZA AL EXCEL BUSCANDO EN LA BASE DE DATOS
@app.route('/buscar_vehiculo/<vehiculo>', methods=['GET'])
def buscar_vehiculo(vehiculo):
    info = InformacionMovil.query.filter_by(vehiculo=vehiculo.strip().upper()).first()
    if info:
        return jsonify({
            "encontrado": True,
            "ruta": info.ruta,
            "tabla": info.tabla,
            "hora": info.hora,
            "novedad": info.novedad
        })
    return jsonify({"encontrado": False})

# -------------------------------------------------------------
# PANEL ADMINISTRATIVO COMPLETO
# -------------------------------------------------------------
@app.route('/admin', methods=['GET'])
def admin_panel():
    if session.get('rol') != 'administrador':
        return redirect(url_for('login'))
        
    todos_los_registros = RegistroVehicular.query.order_by(RegistroVehicular.id.desc()).all()
    usuarios = Usuario.query.all()
    moviles = InformacionMovil.query.all()
    
    return render_template('admin.html', registros=todos_los_registros, usuarios=usuarios, moviles=moviles)

# Crear Usuarios Operadores desde el Panel Administrativo
@app.route('/admin/crear_usuario', methods=['POST'])
def admin_crear_usuario():
    if session.get('rol') != 'administrador': 
        return "No autorizado", 403
        
    username = request.form.get('username').strip().lower()
    password = request.form.get('password').strip()
    nombre = request.form.get('nombre').strip()
    rol = request.form.get('rol')

    if Usuario.query.filter_by(username=username).first():
        flash("El nombre de usuario ya existe en el sistema.", "error")
    else:
        hashed_pw = generate_password_hash(password)
        nuevo_usuario = Usuario(username=username, password_hash=hashed_pw, nombre=nombre, rol=rol)
        db.session.add(nuevo_usuario)
        db.session.commit()
        flash(f"Usuario '{nombre}' creado con éxito.", "success")
        
    return redirect(url_for('admin_panel'))

# Registrar o actualizar los datos del vehículo (Reemplazo del Excel)
@app.route('/admin/guardar_movil', methods=['POST'])
def admin_guardar_movil():
    if session.get('rol') != 'administrador': 
        return "No autorizado", 403
        
    vehiculo = request.form.get('vehiculo').strip().upper()
    ruta = request.form.get('ruta').strip()
    tabla = request.form.get('tabla').strip()
    hora = request.form.get('hora').strip()
    novedad = request.form.get('novedad').strip() or 'SIN NOVEDAD'

    movil = InformacionMovil.query.filter_by(vehiculo=vehiculo).first()
    if movil:
        # Si el vehículo ya existe, actualiza sus campos
        movil.ruta = ruta
        movil.tabla = tabla
        movil.hora = hora
        movil.novedad = novedad
        flash(f"Datos del vehículo {vehiculo} actualizados correctamente.", "success")
    else:
        # Si el vehículo es nuevo, lo registra de cero
        nuevo_movil = InformacionMovil(vehiculo=vehiculo, ruta=ruta, tabla=tabla, hora=hora, novedad=novedad)
        db.session.add(nuevo_movil)
        flash(f"Vehículo {vehiculo} matriculado con éxito en el sistema.", "success")
        
    db.session.commit()
    return redirect(url_for('admin_panel'))

# Limpieza diaria de datos del turno de operaciones (08:00 PM - 04:00 AM)
@app.route('/admin/borrar_todo', methods=['POST'])
def admin_borrar_todo():
    if session.get('rol') != 'administrador': 
        return "No autorizado", 403
        
    try:
        db.session.query(RegistroVehicular).delete()
        db.session.commit()
        flash("Base de datos de registros diarios reiniciada con éxito para el nuevo turno.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al limpiar el historial: {str(e)}", "error")
        
    return redirect(url_for('admin_panel'))

# CREACIÓN INICIAL AUTOMÁTICA DE TABLAS
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
