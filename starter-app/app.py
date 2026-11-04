"""NoteVault secured reference implementation for the term-project laboratory."""
import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from flask_wtf.csrf import CSRFProtect

import jwt

from flask import Flask, Response, jsonify, make_response, redirect, render_template, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
CSRF = CSRFProtect(app)
DB = os.environ.get("NOTEVAULT_DB", "/tmp/notevault.db")
SECRET = os.environ["APP_SECRET"]
if len(SECRET) < 32:
    raise RuntimeError("APP_SECRET must contain at least 32 characters")
app.config["SECRET_KEY"] = SECRET
csrf = CSRFProtect(app)
TEAM_ID = os.environ.get("TEAM_ID", "unassigned")
TEAM_SALT = os.environ.get("TEAM_SALT", "")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
app.config["SESSION_COOKIE_NAME"] = "csrf_session"

def db():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def initialize_db():
    """Create tables only when missing. Never erase existing user data on restart."""
    con = db()
    try:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user');
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY, owner TEXT NOT NULL,
                title TEXT NOT NULL, body TEXT NOT NULL);
        """)
        # Only bootstrap admin on a fresh DB and when the operator supplies a secret.
        if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")
            if password:
                if len(password) < 12:
                    raise RuntimeError("ADMIN_BOOTSTRAP_PASSWORD must be at least 12 characters")
                con.execute(
                    "INSERT INTO users(username,password,role) VALUES(?,?,?)",
                    ("admin", generate_password_hash(password, method="scrypt"), "admin"),
                )
                if TEAM_SALT:
                    marker = hmac.new(TEAM_SALT.encode(), TEAM_ID.encode(), hashlib.sha256).hexdigest()[:12]
                    con.execute(
                        "INSERT INTO notes(owner,title,body) VALUES(?,?,?)",
                        ("admin", "build-tag", f"team={TEAM_ID} marker={marker}"),
                    )
                con.commit()
    finally:
        con.close()


def current_user():
    token = request.cookies.get("session", "")
    if not token:
        return None
    try:
        data = jwt.decode(token, SECRET, algorithms=["HS256"], options={"require": ["sub", "exp", "iat"]})
        username = data.get("sub")
        if not isinstance(username, str):
            return None
        with db() as con:
            row = con.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone()
        return row["username"] if row else None
    except (jwt.InvalidTokenError, ValueError, TypeError):
        return None


def role_of(username):
    with db() as con:
        row = con.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    return row["role"] if row else None


def credentials():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    return (request.form.get("username") or data.get("username"),
            request.form.get("password") or data.get("password"))


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def home():
    user = current_user()
    notes = []
    if user:
        with db() as con:
            notes = con.execute("SELECT id,title,body FROM notes WHERE owner = ?", (user,)).fetchall()
    return render_template("home.html", user=user, is_admin=(user is not None and role_of(user) == "admin"), notes=notes)


@app.post("/register")
def register():
    username, password = credentials()
    if not isinstance(username, str) or not isinstance(password, str) or not username.strip():
        return "invalid registration", 400
    if len(username) > 80 or not (12 <= len(password) <= 1024):
        return "invalid registration", 400
    password_hash = generate_password_hash(password, method="scrypt")
    con = db()
    try:
        con.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)", (username, password_hash, "user"))
        con.commit()
    except sqlite3.IntegrityError:
        return "username already exists", 409
    finally:
        con.close()
    return redirect("/")


@app.post("/login")
def login():
    username, password = credentials()
    if not isinstance(username, str) or not isinstance(password, str):
        return "login failed", 401
    con = db()
    try:
        row = con.execute("SELECT password FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return "login failed", 401
        stored_hash = row["password"]
        # Old MD5 accounts require a password reset; never keep MD5 login paths in production.
        valid = not (len(stored_hash) == 32 and all(c in "0123456789abcdef" for c in stored_hash)) and check_password_hash(stored_hash, password)
        if not valid:
            return "login failed", 401
    finally:
        con.close()
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": username, "iat": now, "exp": now + timedelta(hours=1)}, SECRET, algorithm="HS256")
    response = make_response(redirect("/"))
    response.set_cookie("session", token, httponly=True, secure=COOKIE_SECURE, samesite="Lax", max_age=3600)
    return response


@app.get("/logout")
def logout():
    response = make_response(redirect("/"))
    response.delete_cookie("session")
    return response


@app.post("/notes")
def add_note():
    user = current_user()
    if not user:
        return "auth required", 401
    title, body = request.form.get("title", ""), request.form.get("body", "")
    if len(title) > 200 or len(body) > 10000:
        return "note too long", 400
    with db() as con:
        con.execute("INSERT INTO notes(owner,title,body) VALUES(?,?,?)", (user, title, body))
    return redirect("/")


@app.get("/api/notes/<int:nid>")
def api_note(nid):
    user = current_user()
    if not user:
        return jsonify(error="auth required"), 401
    with db() as con:
        note = con.execute("SELECT id,owner,title,body FROM notes WHERE id = ? AND owner = ?", (nid, user)).fetchone()
    return jsonify(dict(note)) if note else (jsonify(error="not found"), 404)


@app.get("/search")
def search():
    user = current_user()
    if not user:
        return "auth required", 401
    term = request.args.get("q", "")[:200]
    term = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with db() as con:
        notes = con.execute(
            "SELECT title,body FROM notes WHERE owner = ? AND body LIKE ? ESCAPE '\\'",
            (user, f"%{term}%"),
        ).fetchall()
    return render_template("search.html", notes=notes)


@app.get("/admin")
def admin():
    user = current_user()
    if not user or role_of(user) != "admin":
        return "forbidden", 403
    with db() as con:
        rows = con.execute("SELECT id,username,role FROM users").fetchall()
    return jsonify([dict(row) for row in rows])


@app.get("/export")
def export():
    user = current_user()
    if not user:
        return "auth required", 401
    fmt = request.args.get("fmt", "txt")
    if fmt != "txt":
        return "unsupported export format", 400
    with db() as con:
        rows = con.execute("SELECT title,body FROM notes WHERE owner = ?", (user,)).fetchall()
    content = "\n\n".join(f"{row['title']}\n{row['body']}" for row in rows)
    return Response(content, content_type="text/plain; charset=utf-8", headers={"Content-Disposition": "attachment; filename=notes.txt"})


initialize_db()

if __name__ == "__main__":
   app.run(
    host=os.environ.get("BIND_HOST", "127.0.0.1"),
    port=8080,
    debug=False
)