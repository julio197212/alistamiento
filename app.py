import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# CONFIGURACIÓN CRÍTICA DE SEGURIDAD (Corrige el Internal Server Error 500)
# Esto permite guardar los datos de sesión en los celulares sin que el servidor colapse
app.secret_key = 'minga_control_alistamiento_key_secreta'

# Configuración de la Base de Datos SQLite
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'minga.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# MODELO DE LA BASE DE DATOS
class RegistroVehicular(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehiculo = db.Column(db.String(50), nullable=False)
    proceso = db.Column(db.String(100), nullable=False)
    fecha_hora = db.Column(db.String(100), nullable=False)
    observacion = db.Column(db.String(255), nullable=True)

# -------------------------------------------------------------
# RUTAS DE AUTENTICACIÓN (LOGIN / LOGOUT)
# -------------------------------------------------------------
@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_input = request.form.get('usuario').strip().lower()
        contrasena_input = request.form.get('contrasena').strip()
        
        # 1. ACCESO PARA EL ADMINISTRADOR
        if usuario_input == 'administrador' and contrasena_input == 'admin1234':
            session.clear()
            session['nombre'] = 'Administrador'
            session['rol'] = 'administrador'
            return redirect(url_for('admin_panel'))
            
        # 2. ACCESO PARA EL OPERADOR (JONAS)
        elif usuario_input == 'jonas' and contrasena_input == '1234':
            session.clear()
            session['nombre'] = 'Jhonatan Hernandez'
            session['rol'] = 'operador'
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
# RUTA DEL OPERADOR (VISTA Y GUARDADO CON COMPATIBILIDAD AJAX)
# -------------------------------------------------------------
@app.route('/operador', methods=['GET', 'POST'])
def operador():
    if session.get('rol') != 'operador':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        vehiculo = request.form.get('vehiculo')
        proceso = request.form.get('proceso')
        observacion = request.form.get('observacion', 'Ninguna novedad')
        
        # Formateamos la fecha y hora de Colombia
        ahora = datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')
        
        # Guardamos en la base de datos
        nuevo_registro = RegistroVehicular(
            vehiculo=vehiculo,
            proceso=proceso,
            fecha_hora=ahora,
            observacion=observacion
        )
        db.session.add(nuevo_registro)
        db.session.commit()
        
        # RESPUESTA JSON: Evita de raíz que la pantalla de WhatsApp en el celular se quede en negro
        return jsonify({"status": "success", "message": "Registro guardado correctamente"})

    # Carga de la lista (GET)
    procesos_lista = ["Inspección", "Lavado", "Mantenimiento", "Alistamiento Final"]
    ultimos_registros = RegistroVehicular.query.order_by(RegistroVehicular.id.desc()).limit(50).all()
    return render_template('operador.html', procesos=procesos_lista, registros=ultimos_registros)

# -------------------------------------------------------------
# SIMULADOR DE BÚSQUEDA EN EL EXCEL
# -------------------------------------------------------------
@app.route('/buscar_vehiculo/<vehiculo>', methods=['GET'])
def buscar_vehiculo(vehiculo):
    # Aquí puedes integrar tu lógica real de pandas/openpyxl leyendo el archivo de Excel.
    # Por ahora, simulamos una respuesta exitosa si consultan el vehículo 7224:
    if vehiculo == "7224":
        return jsonify({
            "encontrado": True,
            "ruta": "542",
            "tabla": "5",
            "hora": "09:00:00",
            "novedad": "MANTENIMIENTO"
        })
    
    # Datos por defecto si es otro vehículo
    return jsonify({
        "encontrado": True,
        "ruta": "Generica",
        "tabla": "1",
        "hora": "12:00:00",
        "novedad": "SIN NOVEDAD"
    })

# -------------------------------------------------------------
# PANEL DEL ADMINISTRADOR (BORRADO DIARIO DEL TURNO NOCTURNO)
# -------------------------------------------------------------
@app.route('/admin', methods=['GET'])
def admin_panel():
    if session.get('rol') != 'administrador':
        flash("Acceso denegado.", "error")
        return redirect(url_for('login'))
        
    todos_los_registros = RegistroVehicular.query.order_by(RegistroVehicular.id.desc()).all()
    return render_template('admin.html', registros=todos_los_registros)

@app.route('/admin/borrar_todo', methods=['POST'])
def admin_borrar_todo():
    if session.get('rol') != 'administrador':
        return "No autorizado", 403
        
    try:
        # Vaciamos por completo la tabla para reiniciar el turno de 08:00 PM a 04:00 AM
        db.session.query(RegistroVehicular).delete()
        db.session.commit()
        flash("¡Éxito! Base de datos reiniciada para el nuevo turno diario.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al limpiar los datos: {str(e)}", "error")
        
    return redirect(url_for('admin_panel'))

# CREACIÓN AUTOMÁTICA DE TABLAS AL ARRANCAR
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
