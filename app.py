import io
import os
import sqlite3
from datetime import datetime
from functools import wraps
import openpyxl
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file
)
from openpyxl.styles import Font, PatternFill, Alignment
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "CAMBIA-ESTA-CLAVE-SECRETA-ANTES-DE-USAR-EN-RED"
)

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alistamiento.db")

PROCESOS = [
    "Alistamiento",
    "Lavado",
    "Combustible",
    "Inspección",
    "Otro"
]

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        usuario TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        rol TEXT NOT NULL CHECK(rol IN ('admin','operador')),
        activo INTEGER NOT NULL DEFAULT 1,
        creado_en TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS registros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        vehiculo TEXT NOT NULL,
        proceso TEXT NOT NULL,
        fecha_hora TEXT NOT NULL,
        observacion TEXT DEFAULT '',
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    );
    CREATE INDEX IF NOT EXISTS idx_registros_usuario ON registros(usuario_id);
    CREATE INDEX IF NOT EXISTS idx_registros_fecha ON registros(fecha_hora);
    CREATE INDEX IF NOT EXISTS idx_registros_vehiculo ON registros(vehiculo);
    """)

    usuarios_iniciales = [
        ("Administrador", "admin", "Admin123*", "admin"),
        ("Operador 1", "operador1", "Operador123*", "operador"),
        ("Jhonatan Hernandez", "jonas", "253733", "operador"),
        ("Leonard Rojas", "leonard", "256102", "operador"),
        ("Sandro Gomez", "sandro", "256598", "operador"),
        ("Cesar Piñeros", "cesar", "257944", "operador"),
        ("Cristian Muñoz", "cristian", "259399", "operador"),
        ("Yonathan Guillermo", "yonathan", "259555", "operador"),
        ("luis Galindo", "luis", "259608", "operador"),
        ("Jhon Cardenas", "jhon", "260906", "operador"),
        ("Luis buitrago", "luis", "261323", "operador"),
        ("Jorge sanchez", "jorge", "261360", "operador"),
        ("Julio Muñoz", "julio", "julio123", "admin"),
        ("Juan Rojas", "juan", "juan123", "admin"),
        ("Jorge Albaracin", "albjor", "albjor123", "admin"),
        ("Jorge medina", "jormed", "jormed123", "admin"),
        ("Roger Alzate", "roger", "roger123", "admin"),
    ]

    for nombre, usuario, password, rol in usuarios_iniciales:
        existe = conn.execute(
            "SELECT id FROM usuarios WHERE usuario = ?", (usuario,)
        ).fetchone()
        if not existe:
            conn.execute("""
            INSERT INTO usuarios (nombre, usuario, password, rol, activo, creado_en)
            VALUES (?, ?, ?, ?, 1, ?)
            """, (
                nombre,
                usuario,
                generate_password_hash(password),
                rol,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        if session.get("rol") != "admin":
            flash("No tienes permisos para acceder a esta sección.", "danger")
            return redirect(url_for("operador"))
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    if session.get("rol") == "admin":
        return redirect(url_for("admin"))
    return redirect(url_for("operador"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")
        
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE usuario = ? AND activo = 1", (usuario,)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user["password"], password):
            session.clear()
            session["usuario_id"] = user["id"]
            session["nombre"] = user["nombre"]
            session["rol"] = user["rol"]
            return redirect(url_for(
                "admin" if user["rol"] == "admin" else "operador"
            ))
        flash("Usuario o contraseña incorrectos.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/operador", methods=["GET", "POST"])
@login_required
def operador():
    if session.get("rol") != "operador":
        return redirect(url_for("admin"))
        
    if request.method == "POST":
        vehiculo = request.form.get("vehiculo", "").strip().upper()
        proceso = request.form.get("proceso", "").strip()
        observacion = request.form.get("observacion", "").strip()
        
        if not vehiculo:
            flash("Debes ingresar el número del vehículo.", "danger")
        elif proceso not in PROCESOS:
            flash("Selecciona un proceso válido.", "danger")
        else:
            conn = get_db()
            existe = conn.execute("""
            SELECT id FROM registros 
            WHERE usuario_id = ? AND vehiculo = ? AND proceso = ? 
            AND datetime(fecha_hora) >= datetime('now', '-5 minutes')
            """, (session["usuario_id"], vehiculo, proceso)).fetchone()
            
            if existe:
                flash(f"El vehículo {vehiculo} ya fue registrado recientemente para este proceso.", "warning")
            else:
                conn.execute("""
                INSERT INTO registros (usuario_id, vehiculo, proceso, fecha_hora, observacion)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    session["usuario_id"],
                    vehiculo,
                    proceso,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    observacion
                ))
                conn.commit()
                flash(f"Vehículo {vehiculo} registrado correctamente.", "success")
            conn.close()
        return redirect(url_for("operador"))
        
    conn = get_db()
    registros = conn.execute("""
    SELECT * FROM registros WHERE usuario_id = ? ORDER BY id DESC LIMIT 50
    """, (session["usuario_id"],)).fetchall()
    
    total_hoy = conn.execute("""
    SELECT COUNT(*) AS cantidad FROM registros 
    WHERE usuario_id = ? AND date(fecha_hora) = date('now', 'localtime')
    """, (session["usuario_id"],)).fetchone()["cantidad"]
    
    vehiculos_hoy = conn.execute("""
    SELECT COUNT(DISTINCT vehiculo) AS cantidad FROM registros 
    WHERE usuario_id = ? AND date(fecha_hora) = date('now', 'localtime')
    """, (session["usuario_id"],)).fetchone()["cantidad"]
    conn.close()
    
    return render_template(
        "operador.html",
        registros=registros,
        procesos=PROCESOS,
        total_hoy=total_hoy,
        vehiculos_hoy=vehiculos_hoy
    )

@app.route("/admin")
@admin_required
def admin():
    fecha = request.args.get("fecha", "").strip()
    operador_id = request.args.get("operador_id", "").strip()
    vehiculo = request.args.get("vehiculo", "").strip().upper()
    proceso = request.args.get("proceso", "").strip()
    
    conditions = []
    params = []
    
    if fecha:
        conditions.append("date(r.fecha_hora) = ?")
        params.append(fecha)
    if operador_id:
        conditions.append("r.usuario_id = ?")
        params.append(operador_id)
    if vehiculo:
        conditions.append("UPPER(r.vehiculo) LIKE ?")
        params.append(f"%{vehiculo}%")
    if proceso and proceso in PROCESOS:
        conditions.append("r.proceso = ?")
        params.append(proceso)
        
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    
    conn = get_db()
    registros = conn.execute(f"""
    SELECT r.*, u.nombre AS operador, u.usuario 
    FROM registros r 
    JOIN usuarios u ON u.id = r.usuario_id
    {where}
    ORDER BY r.id DESC LIMIT 1000
    """, params).fetchall()
    
    operadores = conn.execute("""
    SELECT id, nombre, usuario FROM usuarios WHERE rol = 'operador' ORDER BY nombre
    """).fetchall()
    
    total = conn.execute(f"""
    SELECT COUNT(*) AS cantidad 
    FROM registros r JOIN usuarios u ON u.id = r.usuario_id {where}
    """, params).fetchone()["cantidad"]
    
    vehiculos_unicos = conn.execute(f"""
    SELECT COUNT(DISTINCT r.vehiculo) AS cantidad 
    FROM registros r JOIN usuarios u ON u.id = r.usuario_id {where}
    """, params).fetchone()["cantidad"]
    
    por_operador = conn.execute(f"""
    SELECT u.nombre AS operador, COUNT(*) AS cantidad 
    FROM registros r JOIN usuarios u ON u.id = r.usuario_id 
    {where} GROUP BY u.id, u.nombre ORDER BY cantidad DESC
    """, params).fetchall()
    
    por_proceso = conn.execute(f"""
    SELECT r.proceso, COUNT(*) AS cantidad 
    FROM registros r JOIN usuarios u ON u.id = r.usuario_id 
    {where} GROUP BY r.proceso ORDER BY cantidad DESC
    """, params).fetchall()
    
    por_fecha = conn.execute(f"""
    SELECT date(r.fecha_hora) AS fecha, COUNT(*) AS cantidad 
    FROM registros r JOIN usuarios u ON u.id = r.usuario_id 
    {where} GROUP BY date(r.fecha_hora) ORDER BY fecha
Usa el código con precaución.
""", params).fetchall()
conn.close()
return render_template(
"admin.html",
registros=registros,
operadores=operadores,
por_operador=por_operador,
por_proceso=por_proceso,
por_fecha=por_fecha,
total=total,
vehiculos_unicos=vehiculos_unicos,
filtros={"fecha": fecha, "operador_id": operador_id, "vehiculo": vehiculo, "proceso": proceso},
procesos=PROCESOS
)
@app.route("/admin/usuarios", methods=["GET", "POST"])
@admin_required
def usuarios():
conn = get_db()
if request.method == "POST":
nombre = request.form.get("nombre", "").strip()
usuario = request.form.get("usuario", "").strip().lower()
password = request.form.get("password", "")
rol = request.form.get("rol", "operador")
if not nombre or not usuario or not password:
flash("Completa todos los campos.", "danger")
elif len(password) < 6:
flash("La contraseña debe tener al menos 6 caracteres.", "danger")
elif rol not in ("admin", "operador"):
flash("Rol no válido.", "danger")
else:
try:
conn.execute("""
INSERT INTO usuarios (nombre, usuario, password, rol, activo, creado_en)
VALUES (?, ?, ?, ?, 1, ?)
""", (
nombre,
usuario,
generate_password_hash(password),
rol,
datetime.now().strftime("%Y-%m-%d %H:%M:%S")
))
conn.commit()
flash("Usuario creado correctamente.", "success")
except sqlite3.IntegrityError:
flash("Ese nombre de usuario ya existe.", "danger")
lista = conn.execute("""
SELECT id, nombre, usuario, rol, activo, creado_en FROM usuarios ORDER BY nombre
""").fetchall()
conn.close()
return render_template("usuarios.html", usuarios=lista)
@app.route("/admin/usuarios/toggle/int:user_id", methods=["POST"])
@admin_required
def toggle_usuario(user_id):
conn = get_db()
user = conn.execute("SELECT activo, rol FROM usuarios WHERE id = ?", (user_id,)).fetchone()
if user:
if user["rol"] == "admin" and user_id == session["usuario_id"]:
flash("No puedes desactivar tu propio usuario administrador.", "warning")
else:
nuevo = 0 if user["activo"] else 1
conn.execute("UPDATE usuarios SET activo = ? WHERE id = ?", (nuevo, user_id))
conn.commit()
flash("Estado del usuario actualizado.", "success")
conn.close()
return redirect(url_for("usuarios"))
@app.route("/exportar")
@admin_required
def exportar():
fecha = request.args.get("fecha", "").strip()
operador_id = request.args.get("operador_id", "").strip()
vehiculo = request.args.get("vehiculo", "").strip().upper()
proceso = request.args.get("proceso", "").strip()
conditions = []
params = []
if fecha:
conditions.append("date(r.fecha_hora) = ?")
params.append(fecha)
if operador_id:
conditions.append("r.usuario_id = ?")
params.append(operador_id)
if vehiculo:
conditions.append("UPPER(r.vehiculo) LIKE ?")
params.append(f"%{vehiculo}%")
if proceso and proceso in PROCESOS:
conditions.append("r.proceso = ?")
params.append(proceso)
where = " WHERE " + " AND ".join(conditions) if conditions else ""
conn = get_db()
rows = conn.execute(f"""
SELECT r.id, u.nombre AS operador, u.usuario, r.vehiculo, r.proceso, r.fecha_hora, r.observacion
FROM registros r
JOIN usuarios u ON u.id = r.usuario_id
{where}
ORDER BY r.fecha_hora DESC
""", params).fetchall()
conn.close()
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Alistamientos"
headers = ["ID", "Operador", "Usuario", "Vehículo", "Proceso", "Fecha y hora", "Observación"]
ws.append(headers)
for row in rows:
ws.append([
row["id"], row["operador"], row["usuario"],
row["vehiculo"], row["proceso"], row["fecha_hora"], row["observacion"]
])
widths = [8, 28, 18, 18, 22, 22, 45]
for i, width in enumerate(widths, start=1):
ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width
ws.freeze_panes = "A2"
ws.auto_filter.ref = ws.dimensions
output = io.BytesIO()
wb.save(output)
output.seek(0)
return send_file(
output,
as_attachment=True,
download_name="reporte_alistamientos.xlsx",
mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
@app.context_processor
def inject_globals():
return {"app_name": "Control de Alistamiento"}
if name == "main":
init_db()
app.run(host="0.0.0.0", port=5000, debug=False)

### Pasos para reactivar:
1. Reemplaza el texto en `app.py` y **guarda el archivo**.
2. Ve a la consola negra de tu computadora y presiona **`Ctrl + C`** para forzar el apagado.
3. Enciende de nuevo el sistema con: `python app.py`
4. Recarga la página en tu celular. El error habrá desaparecido por completo.

<FollowUp>
Por favor, guarda el código, reinicia el servidor y confírmame:
* ¿Ya puedes ver el **login azul en tu teléfono celular** de manera normal?
</FollowUp>
• 
YouTube·Miguel Grinberg
How To Fix an Internal Server Error in Flask
6 ago 2020 — This error is a general catch-all … developers need to examine the terminal session where the Flask server is running. Correcting ...
10:19
