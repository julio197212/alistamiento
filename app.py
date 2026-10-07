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

# Configuración híbrida de Base de Datos (Usa Postgres en internet o SQLite local)
DATABASE_URL = os.environ.get("DATABASE_URL")

PROCESOS = [
    "Alistamiento",
    "Lavado",
    "Combustible",
    "Inspección",
    "Otro"
]

def get_db():
    if DATABASE_URL:
        import psycopg2
        from psycopg2.extras import RealDictRow
        conn = psycopg2.connect(DATABASE_URL)
        # Adaptador para que funcione igual que sqlite3.Row
        conn.cursor_factory = None
        return conn
    else:
        DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alistamiento.db")
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn

def execute_query(query, params=(), fetchall=False, fetchone=False, commit=False):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if commit:
            conn.commit()
            return True
        if fetchall:
            # Normalizar respuesta para conservar compatibilidad de sintaxis de diccionario
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        if fetchone:
            res = cursor.fetchone()
            if res:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, res))
            return None
    except Exception as e:
        print(f"Error en BD: {e}")
        if commit:
            conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def init_db():
    # Creación automática de tablas adaptadas a Postgres o SQLite
    if DATABASE_URL:
        execute_query("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL CHECK(rol IN ('admin','operador')),
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL
        );
        """, commit=True)
        execute_query("""
        CREATE TABLE IF NOT EXISTS registros (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            vehiculo TEXT NOT NULL,
            proceso TEXT NOT NULL,
            fecha_hora TEXT NOT NULL,
            observacion TEXT DEFAULT ''
        );
        """, commit=True)
    else:
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
        conn.commit()
        conn.close()

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
        existe = execute_query("SELECT id FROM usuarios WHERE usuario = ?", (usuario,), fetchone=True)
        if not existe:
            execute_query("""
            INSERT INTO usuarios (nombre, usuario, password, rol, activo, creado_en)
            VALUES (?, ?, ?, ?, 1, ?)
            """, (nombre, usuario, generate_password_hash(password), rol, datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)

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
        
        user = execute_query("SELECT * FROM usuarios WHERE usuario = ? AND activo = 1", (usuario,), fetchone=True)
        
        if user and check_password_hash(user["password"], password):
            session.clear()
            session["usuario_id"] = user["id"]
            session["nombre"] = user["nombre"]
            session["rol"] = user["rol"]
            return redirect(url_for("admin" if user["rol"] == "admin" else "operador"))
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
            # Control de duplicados en ventana de tiempo corta
            time_filter = "datetime('now', '-5 minutes')" if not DATABASE_URL else "NOW() - INTERVAL '5 minutes'"
            date_cast = "datetime(fecha_hora)" if not DATABASE_URL else "CAST(fecha_hora AS TIMESTAMP)"
            
            existe = execute_query(f"""
            SELECT id FROM registros 
            WHERE usuario_id = ? AND vehiculo = ? AND proceso = ? 
            AND {date_cast} >= {time_filter}
            """, (session["usuario_id"], vehiculo, proceso), fetchone=True)
            
            if existe:
                flash(f"El vehículo {vehiculo} ya fue registrado recientemente para este proceso.", "warning")
            else:
                execute_query("""
                INSERT INTO registros (usuario_id, vehiculo, proceso, fecha_hora, observacion)
                VALUES (?, ?, ?, ?, ?)
                """, (session["usuario_id"], vehiculo, proceso, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), observacion), commit=True)
                flash(f"Vehículo {vehiculo} registrado correctamente.", "success")
        return redirect(url_for("operador"))
        
    registros = execute_query("SELECT * FROM registros WHERE usuario_id = ? ORDER BY id DESC LIMIT 50", (session["usuario_id"],), fetchall=True)
    
    date_fn = "date(fecha_hora)" if not DATABASE_URL else "CAST(fecha_hora AS DATE)"
    current_date = "date('now', 'localtime')" if not DATABASE_URL else "CURRENT_DATE"
    
    total_hoy = execute_query(f"SELECT COUNT(*) AS cantidad FROM registros WHERE usuario_id = ? AND {date_fn} = {current_date}", (session["usuario_id"],), fetchone=True)["cantidad"]
    vehiculos_hoy = execute_query(f"SELECT COUNT(DISTINCT vehiculo) AS cantidad FROM registros WHERE usuario_id = ? AND {date_fn} = {current_date}", (session["usuario_id"],), fetchone=True)["cantidad"]
    
    return render_template("operador.html", registros=registros, procesos=PROCESOS, total_hoy=total_hoy, vehiculos_hoy=vehiculos_hoy)

@app.route("/admin")
@admin_required
def admin():
    fecha = request.args.get("fecha", "").strip()
