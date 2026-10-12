import os
from datetime import date, timedelta
from functools import wraps

import mysql.connector
from urllib.parse import unquote, urlparse
from flask import Flask, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")))

def _config():
    # Either one DATABASE_URL (mysql://user:password@host:port/dbname) or separate DB_* variables
    url = os.environ.get("DATABASE_URL") or os.environ.get("DB_URL")
    if url:
        u = urlparse(url)
        cfg = dict(host=u.hostname, port=u.port or 3306, user=unquote(u.username or ""),
                   password=unquote(u.password or ""), database=(u.path or "").lstrip("/") or "library_db")
    else:
        cfg = dict(host=os.environ.get("DB_HOST", "localhost"), port=int(os.environ.get("DB_PORT", "3306")),
                   user=os.environ.get("DB_USER", "root"), password=os.environ.get("DB_PASSWORD", ""),
                   database=os.environ.get("DB_NAME", "library_db"))
    cfg["connection_timeout"] = 10
    ssl = os.environ.get("DB_SSL")  # "1" = on, "0" = off, unset = on for any non-local host
    if ssl == "1" or (ssl is None and cfg["host"] not in ("localhost", "127.0.0.1")):
        cfg["ssl_disabled"] = False
        if os.environ.get("DB_SSL_CA"):
            cfg["ssl_ca"] = os.environ["DB_SSL_CA"]
    return cfg


def db():
    cfg = _config()
    try:
        return mysql.connector.connect(**cfg)
    except mysql.connector.Error as e:
        if getattr(e, "errno", None) != 1049:  # 1049 = database does not exist yet
            raise
        name = cfg.pop("database")
        con = mysql.connector.connect(**cfg)
        cur = con.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}`")
        con.commit()
        cur.close()
        con.close()
        return mysql.connector.connect(database=name, **cfg)


def query(sql, args=(), one=False, commit=False):
    con = db()
    cur = con.cursor(dictionary=True)
    cur.execute(sql, args)
    if commit:
        con.commit()
        result = cur.lastrowid
    else:
        rows = cur.fetchall()
        for r in rows:
            for k, v in r.items():
                if isinstance(v, date):
                    r[k] = v.isoformat()
        result = (rows[0] if rows else None) if one else rows
    cur.close()
    con.close()
    return result


def need(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **k):
            u = session.get("user")
            if not u:
                return jsonify(error="Please log in."), 401
            if roles and u["role"] not in roles:
                return jsonify(error="Only librarians can do this."), 403
            return f(*a, **k)
        return wrapper
    return deco


@app.post("/api/login")
def login():
    d = request.json or {}
    u = query("SELECT * FROM users WHERE username=%s AND role=%s",
              (d.get("username", "").strip(), d.get("role")), one=True)
    if not u or not check_password_hash(u["password_hash"], d.get("password", "")):
        return jsonify(error="Wrong username, password or user type."), 401
    session["user"] = {"id": u["id"], "name": u["full_name"], "role": u["role"]}
    return jsonify(session["user"])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
@need()
def me():
    return jsonify(session["user"])


@app.get("/api/stats")
@need()
def stats():
    s = query("""SELECT COUNT(*) titles,
                 CAST(COALESCE(SUM(available_copies),0) AS SIGNED) available FROM books""", one=True)
    s["issued"] = query("SELECT COUNT(*) n FROM issues WHERE return_date IS NULL", one=True)["n"]
    s["overdue"] = query("SELECT COUNT(*) n FROM issues WHERE return_date IS NULL AND due_date < CURDATE()", one=True)["n"]
    s["members"] = query("SELECT COUNT(*) n FROM users WHERE role <> 'librarian'", one=True)["n"]
    return jsonify(s)


@app.get("/api/books")
@need()
def list_books():
    q = "%" + request.args.get("q", "") + "%"
    return jsonify(query("""SELECT * FROM books WHERE title LIKE %s OR author LIKE %s
                            OR isbn LIKE %s OR category LIKE %s ORDER BY title""", (q, q, q, q)))


@app.post("/api/books")
@need("librarian")
def add_book():
    d = request.json or {}
    copies = int(d.get("copies") or 1)
    try:
        query("""INSERT INTO books (title, author, isbn, category, total_copies, available_copies)
                 VALUES (%s,%s,%s,%s,%s,%s)""",
              (d["title"].strip(), d["author"].strip(), (d.get("isbn") or "").strip() or None,
               d.get("category", "").strip(), copies, copies), commit=True)
    except mysql.connector.IntegrityError:
        return jsonify(error="A book with this ISBN already exists."), 400
    return jsonify(ok=True)


@app.get("/api/users")
@need("librarian")
def list_users():
    return jsonify(query("SELECT id, full_name, username, role FROM users ORDER BY full_name"))


@app.post("/api/users")
@need("librarian")
def add_user():
    d = request.json or {}
    if d.get("role") not in ("student", "member", "librarian"):
        return jsonify(error="Choose a valid user type."), 400
    try:
        query("""INSERT INTO users (full_name, username, email, password_hash, role)
                 VALUES (%s,%s,%s,%s,%s)""",
              (d["full_name"].strip(), d["username"].strip(), d.get("email", "").strip(),
               generate_password_hash(d["password"]), d["role"]), commit=True)
    except mysql.connector.IntegrityError:
        return jsonify(error="That username is already taken."), 400
    return jsonify(ok=True)


@app.get("/api/issues")
@need()
def active_issues():
    u = session["user"]
    sql = """SELECT i.id, b.title, p.full_name, i.issue_date, i.due_date,
                    (i.due_date < CURDATE()) AS overdue
             FROM issues i JOIN books b ON b.id=i.book_id JOIN users p ON p.id=i.user_id
             WHERE i.return_date IS NULL"""
    args = ()
    if u["role"] != "librarian":
        sql += " AND i.user_id=%s"
        args = (u["id"],)
    return jsonify(query(sql + " ORDER BY i.due_date", args))


@app.post("/api/issue")
@need("librarian")
def issue_book():
    d = request.json or {}
    days = int(d.get("days") or 14)
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE books SET available_copies=available_copies-1 WHERE id=%s AND available_copies>0",
                (d["book_id"],))
    if cur.rowcount == 0:
        con.close()
        return jsonify(error="No copies of this book are available."), 400
    cur.execute("INSERT INTO issues (book_id, user_id, issue_date, due_date) VALUES (%s,%s,%s,%s)",
                (d["book_id"], d["user_id"], date.today(), date.today() + timedelta(days=days)))
    con.commit()
    con.close()
    return jsonify(ok=True)


@app.post("/api/return")
@need("librarian")
def return_book():
    issue_id = (request.json or {}).get("issue_id")
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE issues SET return_date=%s WHERE id=%s AND return_date IS NULL", (date.today(), issue_id))
    if cur.rowcount == 0:
        con.close()
        return jsonify(error="This book was already returned."), 400
    cur.execute("UPDATE books b JOIN issues i ON i.book_id=b.id SET b.available_copies=b.available_copies+1 WHERE i.id=%s",
                (issue_id,))
    con.commit()
    con.close()
    return jsonify(ok=True)


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
      id INT AUTO_INCREMENT PRIMARY KEY, full_name VARCHAR(100) NOT NULL,
      username VARCHAR(50) NOT NULL UNIQUE, email VARCHAR(100), password_hash VARCHAR(255) NOT NULL,
      role ENUM('student','member','librarian') NOT NULL DEFAULT 'student',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS books (
      id INT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(200) NOT NULL, author VARCHAR(120) NOT NULL,
      isbn VARCHAR(20) UNIQUE, category VARCHAR(60),
      total_copies INT NOT NULL DEFAULT 1, available_copies INT NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS issues (
      id INT AUTO_INCREMENT PRIMARY KEY, book_id INT NOT NULL, user_id INT NOT NULL,
      issue_date DATE NOT NULL, due_date DATE NOT NULL, return_date DATE NULL,
      FOREIGN KEY (book_id) REFERENCES books(id), FOREIGN KEY (user_id) REFERENCES users(id))""",
]
_ready = False


@app.before_request
def ensure_ready():
    global _ready
    if _ready or not request.path.startswith("/api/"):
        return
    con = db()
    cur = con.cursor()
    for stmt in SCHEMA:
        cur.execute(stmt)
    con.commit()
    cur.close()
    con.close()
    if not query("SELECT id FROM users LIMIT 1", one=True):
        query("INSERT INTO users (full_name, username, email, password_hash, role) VALUES (%s,%s,%s,%s,%s)",
              ("Head Librarian", "admin", "", generate_password_hash("admin123"), "librarian"), commit=True)
    _ready = True


@app.errorhandler(mysql.connector.Error)
def db_error(e):
    n, msg = getattr(e, "errno", None), str(e)
    if n == 1045:
        hint = "wrong database user or password (DB_USER / DB_PASSWORD)."
    elif n == 1049:
        hint = "the database name does not exist and could not be created (check DB_NAME and the user's rights)."
    elif n in (2003, 2005, 2013) or "can't connect" in msg.lower() or "timed out" in msg.lower():
        hint = "cannot reach the database. Check DB_HOST, DB_PORT and the provider's IP allow-list (allow 0.0.0.0/0)."
    else:
        hint = msg
    return jsonify(error="Database error: " + hint), 500


if __name__ == "__main__":
    # Local run: `python api/index.py` serves the frontend and the API together at http://127.0.0.1:5000
    from flask import send_from_directory

    PUBLIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")

    @app.get("/")
    def local_home():
        return send_from_directory(PUBLIC, "index.html")

    @app.get("/<path:name>")
    def local_static(name):
        return send_from_directory(PUBLIC, name)

    app.run(debug=True)
