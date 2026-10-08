import io, os, sqlite3, openpyxl
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from openpyxl.styles import Font, PatternFill, Alignment
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CLAVE-SECRETA-PRODUCCION-2026")
DATABASE_URL = os.environ.get("DATABASE_URL")
PROCESOS = ["Alistamiento", "Lavado", "Combustible", "Inspección", "Otro"]

def get_db():
    if DATABASE_URL:
        import psycopg2, psycopg2.extras
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alistamiento.db")
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=(), fetchall=False, fetchone=False, commit=False):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if commit: conn.commit(); return True
        if fetchall: return cursor.fetchall()
        if fetchone: return cursor.fetchone()
    except Exception as e:
        if commit: conn.rollback()
        raise e
    finally: cursor.close(); conn.close()

def init_db():
    if DATABASE_URL:
        execute_query("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT, usuario TEXT UNIQUE, password TEXT, rol TEXT, activo INTEGER DEFAULT 1, creado_en TEXT);", commit=True)
        execute_query("CREATE TABLE IF NOT EXISTS registros (id SERIAL PRIMARY KEY, usuario_id INTEGER, vehiculo TEXT, proceso TEXT, fecha_hora TEXT, observacion TEXT DEFAULT '');", commit=True)
    else:
        conn = get_db()
        conn.executescript("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, usuario TEXT UNIQUE, password TEXT, rol TEXT, activo INTEGER DEFAULT 1, creado_en TEXT); CREATE TABLE IF NOT EXISTS registros (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, vehiculo TEXT, proceso TEXT, fecha_hora TEXT, observacion TEXT DEFAULT '');")
        conn.commit(); conn.close()
    if not execute_query("SELECT id FROM usuarios WHERE usuario = 'admin';", fetchone=True):
        execute_query("INSERT INTO usuarios (nombre, usuario, password, rol, activo, creado_en) VALUES ('Administrador', 'admin', ?, 'admin', 1, ?);", (generate_password_hash("Admin123*"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
    if not execute_query("SELECT id FROM usuarios WHERE usuario = 'jonas';", fetchone=True):
        execute_query("INSERT INTO usuarios (nombre, usuario, password, rol, activo, creado_en) VALUES ('Jhonatan Hernandez', 'jonas', ?, 'operador', 1, ?);", (generate_password_hash("253733"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session: return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session: return redirect(url_for("login"))
        if session.get("rol") != "admin": flash("No tienes permisos.", "danger"); return redirect(url_for("operador"))
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    if "usuario_id" not in session: return redirect(url_for("login"))
    return redirect(url_for("admin" if session.get("rol") == "admin" else "operador"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip().lower()
        password = request.form.get("password", "")
        user = execute_query("SELECT * FROM usuarios WHERE usuario = ? AND activo = 1", (usuario,), fetchone=True)
        if user and check_password_hash(user["password"], password):
            session.clear(); session["usuario_id"] = user["id"]; session["nombre"] = user["nombre"]; session["rol"] = user["rol"]
            return redirect(url_for("admin" if user["rol"] == "admin" else "operador"))
        flash("Usuario o contraseña incorrectos.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/operador", methods=["GET", "POST"])
@login_required
def operador():
    if session.get("rol") != "operador": return redirect(url_for("admin"))
    if request.method == "POST":
        vehiculo = request.form.get("vehiculo", "").strip().upper()
        proceso = request.form.get("proceso", "").strip()
        observacion = request.form.get("observacion", "").strip()
        if not vehiculo or proceso not in PROCESOS: flash("Datos inválidos.", "danger")
        else:
            execute_query("INSERT INTO registros (usuario_id, vehiculo, proceso, fecha_hora, observacion) VALUES (?, ?, ?, ?, ?)", (session["usuario_id"], vehiculo, proceso, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), observacion), commit=True)
            flash(f"Vehículo {vehiculo} registrado correctamente.", "success")
        return redirect(url_for("operador"))
    registros = execute_query("SELECT * FROM registros WHERE usuario_id = ? ORDER BY id DESC LIMIT 50", (session["usuario_id"],), fetchall=True)
    return render_template("operador.html", registros=registros, procesos=PROCESOS, total_hoy=len(registros), vehiculos_hoy=len(registros))

@app.route("/admin")
@admin_required
def admin():
    registros = execute_query("SELECT r.*, u.nombre AS operador FROM registros r JOIN usuarios u ON u.id = r.usuario_id ORDER BY r.id DESC LIMIT 1000", fetchall=True)
    operadores = execute_query("SELECT id, nombre FROM usuarios WHERE rol = 'operador'", fetchall=True)
    return render_template("admin.html", registros=registros, operadores=operadores, por_operador=[], por_proceso=[], por_fecha=[], total=len(registros), vehiculos_unicos=len(registros), filtros={}, procesos=PROCESOS)

@app.route("/admin/usuarios", methods=["GET", "POST"])
@admin_required
def usuarios():
    if request.method == "POST":
        nombre, usuario, password = request.form.get("nombre", "").strip(), request.form.get("usuario", "").strip().lower(), request.form.get("password", "")
        if nombre and usuario and password:
            try:
                execute_query("INSERT INTO usuarios (nombre, usuario, password, rol, activo, creado_en) VALUES (?, ?, ?, 'operador', 1, ?)", (nombre, usuario, generate_password_hash(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
                flash("Usuario creado.", "success")
            except: flash("El usuario ya existe.", "danger")
    lista = execute_query("SELECT id, nombre, usuario, rol, activo, creado_en FROM usuarios ORDER BY nombre", fetchall=True)
    return render_template("usuarios.html", usuarios=lista)

@app.route("/exportar")
@admin_required
def exportar():
    rows = execute_query("SELECT r.id, u.nombre AS operador, r.vehiculo, r.proceso, r.fecha_hora, r.observacion FROM registros r JOIN usuarios u ON u.id = r.usuario_id ORDER BY r.id DESC", fetchall=True)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Alistamientos"
    ws.append(["ID", "Operador", "Vehículo", "Proceso", "Fecha y hora", "Observación"])
    for r in rows: ws.append([r["id"], r["operador"], r["vehiculo"], r["proceso"], r["fecha_hora"], r["observacion"]])
    for col in ws.columns: ws.column_dimensions[openpyxl.utils.get_column_letter(col[0].column)].width = 20
    output = io.BytesIO(); wb.save(output); output.seek(0)
    return send_file(output, as_attachment=True, download_name="reporte.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
