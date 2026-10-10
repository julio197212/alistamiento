import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# 1. INICIALIZACIÓN DE LA APLICACIÓN FLASK
app = Flask(__name__)

# LLAVE DE SEGURIDAD CRÍTICA PARA INICIOS DE SESIÓN EN NAVEGADORES MÓVILES
app.secret_key = 'minga_control_alistamiento_key_secreta_2026'

# Configuración de la Base de Datos SQLite Local Limpia
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'minga_final_v3.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 2. INICIALIZACIÓN CORRECTA DE SQLALCHEMY
db = SQLAlchemy()
db.init_app(app)

# -------------------------------------------------------------
# MODELOS DE LA BASE DE DATOS
# -------------------------------------------------------------
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), default='operador') 

class InformacionMovil(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehiculo = db.Column(db.String(50), unique=True, nullable=False) 
    ruta = db.Column(db.String(50), nullable=False)
    tabla = db.Column(db.String(50), nullable=False)
    hora = db.Column(db.String(50), nullable=False)
    novedad = db.Column(db.String(255), default='SIN NOVEDAD')

class RegistroVehicular(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehiculo = db.Column(db.String(50), nullable=False)
    proceso = db.Column(db.String(100), nullable=False)
    fecha_hora = db.Column(db.String(100), nullable=False)
    observacion = db.Column(db.String(255), nullable=True)
    operador = db.Column(db.String(100), nullable=True) # <-- AGREGAR ESTA LÍNEA

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
        usuario_input = (request.form.get('usuario') or 
                         request.form.get('username') or 
                         request.form.get('user') or 
                         request.form.get('txt_usuario') or '').strip().lower()
                         
        contrasena_input = (request.form.get('contrasena') or 
                            request.form.get('password') or 
                            request.form.get('pass') or 
                            request.form.get('txt_contrasena') or '').strip()
        
        # ACCESO MAESTRO GENERAL PREDETERMINADO
        if usuario_input == 'administrador' and contrasena_input == 'admin1234':
            session.clear()
            session['nombre'] = 'Administrador General'
            session['rol'] = 'administrador'
            return redirect(url_for('admin_panel'))

        # DICCIONARIO DE CREDENCIALES COMPLETAS DEL PERSONAL (BLINDADO CONTRA BORRADOS)
        usuarios_fijos = {
            "julio": {"pass": "julio123", "nombre": "Julio Muñoz", "rol": "administrador"},
            "juan": {"pass": "juan123", "nombre": "Juan Rojas", "rol": "administrador"},
            "jorge.albarracin": {"pass": "jorgea123", "nombre": "Jorge Albarracin", "rol": "administrador"},
            "jorge.medina": {"pass": "jorgem123", "nombre": "Jorge medina", "rol": "administrador"},
            "roger": {"pass": "roger123", "nombre": "Roger Alzate", "rol": "administrador"},
            "operador1": {"pass": "Operador123*", "nombre": "Operador 1", "rol": "operador"},
            "jonas": {"pass": "253733", "nombre": "Jhonatan Hernandez", "rol": "operador"},
            "leonard": {"pass": "256102", "nombre": "Leonard Rojas", "rol": "operador"},
            "sandro": {"pass": "256598", "nombre": "Sandro Gomez", "rol": "operador"},
            "cesar": {"pass": "257944", "nombre": "Cesar Piñeros", "rol": "operador"},
            "cristian": {"pass": "259399", "nombre": "Cristian Muñoz", "rol": "operador"},
            "yonathan": {"pass": "259555", "nombre": "Yonathan Guillermo", "rol": "operador"},
            "luis.galindo": {"pass": "259608", "nombre": "luis Galindo", "rol": "operador"},
            "jhon": {"pass": "260906", "nombre": "Jhon Cardenas", "rol": "operador"},
            "luis.buitrago": {"pass": "261323", "nombre": "Luis buitrago", "rol": "operador"},
            "jorge.sanchez": {"pass": "261360", "nombre": "Jorge sanchez", "rol": "operador"},
        }

        if usuario_input in usuarios_fijos:
            datos_user = usuarios_fijos[usuario_input]
            if contrasena_input == datos_user["pass"]:
                session.clear()
                session['nombre'] = datos_user["nombre"]
                session['rol'] = datos_user["rol"]
                
                if datos_user["rol"] == 'administrador':
                    return redirect(url_for('admin_panel'))
                return redirect(url_for('operador'))

        try:
            user = Usuario.query.filter_by(username=usuario_input).first()
            if user and check_password_hash(user.password_hash, contrasena_input):
                session.clear()
                session['user_id'] = user.id
                session['nombre'] = user.nombre
                session['rol'] = user.rol
                if user.rol == 'administrador':
                    return redirect(url_for('admin_panel'))
                return redirect(url_for('operador'))
        except Exception:
            pass

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
        
        ahora = datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')
        
                   <!-- TARJETA: CARGAR INFORMACIÓN DE MÓVILES (REEMPLAZO EXCEL) -->
    <div style="background: white; border-radius: 12px; padding: 20px; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-top: 4px solid #0d6efd;">
        <h4 style="margin: 0 0 5px 0; color: #1e293b;">🚍 Cargar / Actualizar Datos del Móvil</h4>
        <p style="margin: 0 0 15px 0; font-size: 0.85rem; color: #64748b;">Si el número de vehículo ya existe, actualizará sus datos; si no, creará uno nuevo.</p>
        <form action="/admin/guardar_movil" method="POST" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px;">
            <input type="text" name="vehiculo" required placeholder="Vehículo / Placa (7211)" style="padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px; text-transform: uppercase;">
            <input type="text" name="ruta" required placeholder="Ruta (Ej. 542)" style="padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px;">
            <input type="text" name="tabla" required placeholder="Tabla (Ej. 3)" style="padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px;">
            <input type="text" name="hora" required placeholder="Hora (Ej. 08:30 PM)" style="padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px;">
            <input type="text" name="novedad" placeholder="Novedad (Opcional)" style="padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px;">
            <button type="submit" style="padding: 10px; background: #0d6efd; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer;">Explicitly Guardar Móvil</button>
        </form>
    </div>

    <!-- TARJETA: REINICIAR REGISTROS DIARIOS -->
    <div style="background: white; border-radius: 12px; padding: 20px; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-top: 4px solid #dc3545;">
        <h4 style="margin: 0 0 10px 0; color: #1e293b;">🗑️ Mantenimiento de Turno Operativo</h4>
        <form action="/admin/borrar_todo" method="POST" onsubmit="return confirm('¿Borrar todos los registros del turno? No afectará a las rutas creadas.');">
            <button type="submit" style="width: 100%; padding: 12px; background: #dc3545; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer;">
                Limpiar Historial de Registros Diarios (08:00 PM - 04:00 AM)
            </button>
        </form>
    </div>

    <!-- CORREGIDO: NUEVA TABLA MONITOR DE REGISTROS CON CUADROS DE FILTRADO -->
    <div style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); overflow-x: auto; -webkit-overflow-scrolling: touch;">
        <h4 style="margin: 0 0 5px 0; color: #1e293b;">📋 Monitor de Registros del Turno</h4>
        <p style="margin: 0 0 15px 0; font-size: 0.85rem; color: #64748b;">Escriba en las casillas de abajo para buscar por número de móvil o por operario en tiempo real.</p>
        
        <!-- BUSCADORES FLOTANTES EN PANTALLA -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
            <div>
                <label style="display: block; font-size: 0.8rem; font-weight: bold; color: #475569; margin-bottom: 5px; text-transform: uppercase;">Filtrar por Móvil</label>
                <input type="text" id="filtro_movil" onkeyup="aplicarFiltros()" placeholder="Ej. 7224" 
                       style="width: 100%; padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; text-transform: uppercase;">
            </div>
            <div>
                <label style="display: block; font-size: 0.8rem; font-weight: bold; color: #475569; margin-bottom: 5px; text-transform: uppercase;">Filtrar por Operador</label>
                <input type="text" id="filtro_operador" onkeyup="aplicarFiltros()" placeholder="Ej. Jhonatan" 
                       style="width: 100%; padding: 10px; border: 1.5px solid #cbd5e1; border-radius: 6px; box-sizing: border-box;">
            </div>
        </div>

        <div style="width: 100%; overflow-x: auto;">
            <table style="width: 100%; min-width: 700px; border-collapse: collapse; font-size: 0.9rem;">
                <thead>
                    <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1; text-align: left;">
                        <th style="padding: 10px;">Vehículo</th>
                        <th style="padding: 10px;">Operador</th>
                        <th style="padding: 10px;">Proceso</th>
                        <th style="padding: 10px;">Fecha / Hora</th>
                        <th style="padding: 10px;">Observación</th>
                    </tr>
                </thead>
                <tbody>
                    {% for r in registros %}
                    <tr class="fila-registro" style="border-bottom: 1px solid #e2e8f0;">
                        <td class="celda-movil" style="padding: 10px; font-weight: bold; color: #0d6efd;">{{ r.vehiculo }}</td>
                        <td class="celda-operador" style="padding: 10px; color: #1e293b; font-weight: 500;">{{ r.operador or 'Jhonatan Hernandez' }}</td>
                        <td style="padding: 10px;"><span style="background: #e0f2fe; color: #0369a1; padding: 3px 6px; border-radius: 4px; font-weight: 600;">{{ r.proceso }}</span></td>
                        <td style="padding: 10px; color: #64748b;">{{ r.fecha_hora }}</td>
                        <td style="padding: 10px; color: #475569;">{{ r.observacion }}</td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="5" style="padding: 20px; text-align: center; color: #94a3b8; font-style: italic;">No hay registros cargados. Base de datos vacía.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- SCRIPT DE INTERACCIÓN DEL GRÁFICO Y FILTRADO DIARIO -->
<script>
function aplicarFiltros() {
    const buscarMovil = document.getElementById("filtro_movil").value.toUpperCase().trim();
    const buscarOperador = document.getElementById("filtro_operador").value.toLowerCase().trim();
    const filas = document.getElementsByClassName("fila-registro");

    for (let i = 0; i < filas.length; i++) {
        const textoMovil = filas[i].querySelector(".celda-movil").innerText.toUpperCase();
        const textoOperador = filas[i].querySelector(".celda-operador").innerText.toLowerCase();

        const coincideMovil = textoMovil.includes(buscarMovil);
        const coincideOperador = textoOperador.includes(buscarOperador);

        if (coincideMovil && coincideOperador) {
            filas[i].style.display = ""; 
        } else {
            filas[i].style.display = "none"; 
        }
    }
}

// Código del gráfico de barras Chart.js
const ctx = document.getElementById('graficoProcesos').getContext('2d');
new Chart(ctx, {
    type: 'bar',
    data: {
        labels: ['Inspección', 'Lavado', 'Mantenimiento', 'Alistamiento Final'],
        datasets: [{
            data: [
                {{ conteo['Inspección'] }}, 
                {{ conteo['Lavado'] }}, 
                {{ conteo['Mantenimiento'] }}, 
                {{ conteo['Alistamiento Final'] }}
            ],
            backgroundColor: ['rgba(13, 110, 253, 0.75)', 'rgba(16, 185, 129, 0.75)', 'rgba(245, 158, 11, 0.75)', 'rgba(107, 114, 128, 0.75)'],
            borderColor: ['#0d6efd', '#10b981', '#f59e0b', '#6b7280'],
            borderWidth: 1.5,
            borderRadius: 4
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, ticks: { stepSize: 1, color: '#64748b' }, grid: { color: '#e2e8f0' } },
            x: { ticks: { color: '#475569', font: { weight: '600', size: 11 } }, grid: { display: false } }
        }
    }
});
</script>
{% endblock %}

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
            
        return jsonify({"status": "success", "message": "Registro guardado correctamente"})

    procesos_lista = ["Inspección", "Lavado", "Mantenimiento", "Alistamiento Final"]
    ultimos_registros = []
    try:
        ultimos_registros = RegistroVehicular.query.order_by(RegistroVehicular.id.desc()).limit(50).all()
    except Exception:
        pass
    return render_template('operador.html', procesos=procesos_lista, registros=ultimos_registros)

# BUSCADOR DINÁMICO QUE SUSTITUYE AL EXCEL CONSULTANDO LA BASE DE DATOS
@app.route('/buscar_vehiculo/<vehiculo>', methods=['GET'])
def buscar_vehiculo(vehiculo):
    try:
        info = InformacionMovil.query.filter_by(vehiculo=vehiculo.strip().upper()).first()
        if info:
            return jsonify({
                "encontrado": True,
                "ruta": info.ruta,
                "tabla": info.tabla,
                "hora": info.hora,
                "novedad": info.novedad
            })
    except Exception:
        pass
    return jsonify({"encontrado": False})

# -------------------------------------------------------------
# PANEL ADMINISTRATIVO COMPLETO CON REPORTE DE WHATSAPP
# -------------------------------------------------------------
# -------------------------------------------------------------
# PANEL ADMINISTRATIVO COMPLETO CON TEXTO LIMPIO PARA WHATSAPP
# -------------------------------------------------------------
@app.route('/admin', methods=['GET'])
def admin_panel():
    if session.get('rol') != 'administrador':
        return redirect(url_for('login'))
        
    todos_los_registros = []
    moviles = []
    
    conteo_procesos = {
        "Inspección": 0,
        "Lavado": 0,
        "Mantenimiento": 0,
        "Alistamiento Final": 0
    }
    
    try:
        todos_los_registros = RegistroVehicular.query.order_by(RegistroVehicular.id.desc()).all()
        moviles = InformacionMovil.query.all()
        
        for r in todos_los_registros:
            if r.proceso in conteo_procesos:
                conteo_procesos[r.proceso] += 1
                
    except Exception:
        pass

    # REDACCIÓN LIMPIA CON TEXTO PLANO SEGURO
    fecha_reporte = datetime.now().strftime('%d/%m/%Y')
    mensaje_whatsapp = (
        f"📋 *REPORTE DE ALISTAMIENTO MINGA*\n"
        f"📅 *Fecha:* {fecha_reporte}\n"
        f"----------------------------------------\n"
        f"📊 *Resumen de Procesos del Turno:*\n"
        f"🔍 Inspecciones: {conteo_procesos['Inspección']}\n"
        f"🧼 Lavados: {conteo_procesos['Lavado']}\n"
        f"🔧 Mantenimientos: {conteo_procesos['Mantenimiento']}\n"
        f"✨ Alistamientos Finales: {conteo_procesos['Alistamiento Final']}\n"
        f"----------------------------------------\n"
        f"🚗 *Total Vehículos Procesados:* {len(todos_los_registros)}\n\n"
        f"¡Sistema MINGA Operativo! ✅"
    )
        
    return render_template(
        'admin.html', 
        registros=todos_los_registros, 
        moviles=moviles,
        conteo=conteo_procesos,
        mensaje_wa=mensaje_whatsapp
    )

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

    try:
        movil = InformacionMovil.query.filter_by(vehiculo=vehiculo).first()
        if movil:
            movil.ruta = ruta
            movil.tabla = tabla
            movil.hora = hora
            movil.novedad = novedad
            flash(f"Datos del vehículo {vehiculo} actualizados correctamente.", "success")
        else:
            nuevo_movil = InformacionMovil(vehiculo=vehiculo, ruta=ruta, tabla=tabla, hora=hora, novedad=novedad)
            db.session.add(nuevo_movil)
            flash(f"Vehículo {vehiculo} matriculado con éxito en el sistema.", "success")
        db.session.commit()
    except Exception as e:
        flash(f"Error al guardar datos del móvil: {str(e)}", "error")
        
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

# CREACIÓN INICIAL AUTOMÁTICA DE TABLAS AL ARRANCAR
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
