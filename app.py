import io, os, sqlite3, openpyxl
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from openpyxl.styles import Font, PatternFill, Alignment
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "MINGA_CONTROL_TRANSPORTE_SEGURO_2026"
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

DATABASE_URL = os.environ.get("DATABASE_URL")
PROCESOS = ["Alistamiento", "Lavado", "Combustible", "Inspección", "Otro"]

def get_db():
    if DATABASE_URL:
        import psycopg2, psycopg2.extras
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor, sslmode='require')
    DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alistamiento.db")
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=(), fetchall=False, fetchone=False, commit=False):
    # TRADUCTOR SEGURO: Solo cambia marcadores, nunca toca los datos de las contraseñas
    if DATABASE_URL:
        query = query.replace("?", "%s")
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
        execute_query("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT, usuario TEXT UNIQUE, password VARCHAR(500), rol TEXT, activo INTEGER DEFAULT 1, creado_en TEXT);", commit=True)
        execute_query("CREATE TABLE IF NOT EXISTS registros (id SERIAL PRIMARY KEY, usuario_id INTEGER, vehiculo TEXT, proceso TEXT, fecha_hora TEXT, observacion TEXT DEFAULT '');", commit=True)
    else:
        conn = get_db()
        conn.executescript("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, usuario TEXT UNIQUE, password TEXT, rol TEXT, activo INTEGER DEFAULT 1, creado_en TEXT); CREATE TABLE IF NOT EXISTS registros (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, vehiculo TEXT, proceso TEXT, fecha_hora TEXT, observacion TEXT DEFAULT '');")
        conn.commit(); conn.close()
    
    # Inserción segura nativa para PostgreSQL en Internet sin usar el traductor en texto plano
    try:
        if DATABASE_URL:
            # Forzamos la creación manual con %s para evitar choques en el primer encendido
            admin = execute_query("SELECT id FROM usuarios WHERE usuario = 'admin';", fetchone=True)
            if not admin:
                execute_query("INSERT INTO usuarios (nombre, usuario, password, rol, activo, creado_en) VALUES ('Administrador', 'admin', %s, 'admin', 1, %s);", (generate_password_hash("Admin123*"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
            jonas = execute_query("SELECT id FROM usuarios WHERE usuario = 'jonas';", fetchone=True)
            if not jonas:
                execute_query("INSERT INTO usuarios (nombre, usuario, password, rol, activo, creado_en) VALUES ('Jhonatan Hernandez', 'jonas', %s, 'operador', 1, %s);", (generate_password_hash("253733"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
        else:
            if not execute_query("SELECT id FROM usuarios WHERE usuario = 'admin';", fetchone=True):
                execute_query("INSERT INTO usuarios (nombre, usuario, password, rol, activo, creado_en) VALUES ('Administrador', 'admin', ?, 'admin', 1, ?);", (generate_password_hash("Admin123*"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
            if not execute_query("SELECT id FROM usuarios WHERE usuario = 'jonas';", fetchone=True):
                execute_query("INSERT INTO usuarios (nombre, usuario, password, rol, activo, creado_en) VALUES ('Jhonatan Hernandez', 'jonas', ?, 'operador', 1, ?);", (generate_password_hash("253733"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
    except Exception as e: print(e)

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

@app.route("/buscar_vehiculo/<numero>")
@login_required
def buscar_vehiculo(numero):
    excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos.xlsx")
    if not os.path.exists(excel_path): return jsonify({"encontrado": False, "msg": "Archivo no encontrado"})
    try:
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and len(row) >= 5 and str(row[0]).strip().upper() == str(numero).strip().upper():
                return jsonify({"encontrado": True, "ruta": str(row[1]) if row[1] is not None else "-", "tabla": str(row[2]) if row[2] is not None else "-", "hora": str(row[3]) if row[3] is not None else "-", "novedad": str(row[4]) if row[4] is not None else "-"})
    except Exception as e: return jsonify({"encontrado": False, "msg": str(e)})
    return jsonify({"encontrado": False})

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip().lower()
        password = request.form.get("password", "")
        # Ajustamos a formato seguro nativo para internet
        q = "SELECT * FROM usuarios WHERE usuario = %s AND activo = 1" if DATABASE_URL else "SELECT * FROM usuarios WHERE usuario = ? AND activo = 1"
        user = execute_query(q, (usuario,), fetchone=True)
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
            q = "INSERT INTO registros (usuario_id, vehiculo, proceso, fecha_hora, observacion) VALUES (%s, %s, %s, %s, %s)" if DATABASE_URL else "INSERT INTO registros (usuario_id, vehiculo, proceso, fecha_hora, observacion) VALUES (?, ?, ?, ?, ?)"
            execute_query(q, (session["usuario_id"], vehiculo, proceso, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), observacion), commit=True)
            flash(f"Vehículo {vehiculo} registrado correctamente.", "success")
        return redirect(url_for("operador"))
    q_reg = "SELECT * FROM registros WHERE usuario_id = %s ORDER BY id DESC LIMIT 50" if DATABASE_URL else "SELECT * FROM registros WHERE usuario_id = ? ORDER BY id DESC LIMIT 50"
    registros = execute_query(q_reg, (session["usuario_id"],), fetchall=True)
    return render_template("operador.html", registros=registros, procesos=PROCESOS, total_hoy=len(registros), vehiculos_hoy=len(registros))

@app.route("/admin")
@admin_required
def admin():
    operador_id = request.args.get("operador_id", "").strip()
    vehiculo = request.args.get("vehiculo", "").strip().upper()
    conditions = []
    params = []
    if operador_id:
        conditions.append("r.usuario_id = %s" if DATABASE_URL else "r.usuario_id = ?")
        params.append(int(operador_id))
    if vehiculo:
        conditions.append("UPPER(r.vehiculo) LIKE %s" if DATABASE_URL else "UPPER(r.vehiculo) LIKE ?")
        params.append(f"%{vehiculo}%")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    query_base = f"SELECT r.id, u.nombre AS operador, r.vehiculo, r.proceso, r.fecha_hora, r.observacion FROM registros r JOIN usuarios u ON u.id = r.usuario_id {where} ORDER BY r.id DESC LIMIT 1000"
    registros = execute_query(query_base, params, fetchall=True)
    operadores = execute_query("SELECT id, nombre FROM usuarios WHERE rol = 'operador' ORDER BY nombre", fetchall=True)
    total = len(registros)
    vehiculos_unicos = len(set([r['vehiculo'] for r in registros])) if registros else 0
    return render_template("admin.html", registros=registros, operadores=operadores, total=total, vehiculos_unicos=vehiculos_unicos)

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
