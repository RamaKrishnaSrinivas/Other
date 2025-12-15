import os
import csv
from flask import Flask, render_template_string, request, redirect, url_for, flash, session, Response
from flask_bcrypt import Bcrypt
import psycopg2
import urllib.parse as up
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ---------------- Load environment variables ----------------
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback_secret_key')
bcrypt = Bcrypt(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["5 per minute"],
    storage_uri="memory://",  # Or Redis/Memcached for production
)

# ---------------- Database URL ----------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://oruganti_01wi_user:m3CXA5cRcgA7iIZJhnByQSzszqK538Fv@dpg-d3ihh32dbo4c73fobeeg-a.oregon-postgres.render.com/oruganti_01wi"
)

OWNER_DOWNLOAD_KEY = os.getenv("OWNER_DOWNLOAD_KEY", "skro@0513")

# ---------------- Database connection ----------------
def connect_to_db():
    try:
        up.uses_netloc.append("postgres")
        url = up.urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to DB: {e}")
        return None

# ---------------- Create users table ----------------
def create_table():
    conn = connect_to_db()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    dob DATE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

create_table()

# ---------------- Basic CSS ----------------
base_style = """
<style>
body { font-family: Arial, sans-serif; background: #f0f2f5; margin:0; padding:0; }
.container { width: 350px; margin: 50px auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
h1 { text-align: center; color: #333; }
label { display: block; margin-top: 10px; color: #555; }
input[type=text], input[type=email], input[type=password], input[type=date] {
    width: 100%; padding: 8px; margin-top: 5px; border-radius: 4px; border: 1px solid #ccc;
}
input[type=submit] { width: 100%; padding: 10px; margin-top: 15px; background: #4CAF50; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
input[type=submit]:hover { background: #45a049; }
ul { list-style-type: none; padding: 0; }
li { margin: 5px 0; color: red; text-align: center; }
a { color: #4CAF50; text-decoration: none; }
a:hover { text-decoration: underline; }
nav ul { text-align: center; }
nav ul li { display: inline; margin: 0 10px; }
</style>
"""

# ---------------- Templates ----------------
index_template = base_style + """
<div class="container">
    <nav>
        <ul>
            <li><a href="{{ url_for('register') }}">Register</a></li>
            <li><a href="{{ url_for('login') }}">Login</a></li>
        </ul>
    </nav>
    <h1>Welcome</h1>
</div>
"""

form_template = base_style + """
<div class="container">
    <h1>{{ title }}</h1>
    <form method="POST">
        {% for field in fields %}
            <label>{{ field.label }}</label>
            <input type="{{ field.type }}" name="{{ field.name }}" {% if field.required %}required{% endif %}>
        {% endfor %}
        <input type="submit" value="{{ button }}">
    </form>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <ul>
        {% for category, message in messages %}
          <li>{{ message }}</li>
        {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}
    {% if extra_link %}
        <p style="text-align:center; margin-top:10px;"><a href="{{ extra_link.url }}">{{ extra_link.text }}</a></p>
    {% endif %}
</div>
"""

dashboard_template = base_style + """
<div class="container">
    <h1>Dashboard</h1>
    <p>Welcome, {{ session['user'] }}!</p>
    <p style="text-align:center;"><a href="{{ url_for('logout') }}">Logout</a></p>
</div>
"""

# ---------------- Routes ----------------
@app.route('/')
def index():
    return render_template_string(index_template)

@app.route('/register', methods=['GET', 'POST'])
def register():
    fields = [
        {"label": "Name", "type": "text", "name": "name", "required": True},
        {"label": "Date of Birth", "type": "date", "name": "dob", "required": True},
        {"label": "Email", "type": "email", "name": "email", "required": True},
        {"label": "Password", "type": "password", "name": "password", "required": True}
    ]
    if request.method == 'POST':
        name = request.form['name']
        dob = request.form['dob']
        email = request.form['email']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = connect_to_db()
        if conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO users (name, dob, email, password) VALUES (%s,%s,%s,%s)",
                    (name, dob, email, hashed_password)
                )
                conn.commit()
                flash("Registration successful!", "green")
                return redirect(url_for('login'))
            except psycopg2.Error:
                flash("Email already exists or DB error!", "red")
            finally:
                conn.close()

    return render_template_string(
        form_template, title="Register", fields=fields, button="Register",
        extra_link={"url": url_for('login'), "text": "Already have an account? Login"}
    )

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    fields = [
        {"label": "Email", "type": "email", "name": "email", "required": True},
        {"label": "Password", "type": "password", "name": "password", "required": True}
    ]
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = connect_to_db()
        if conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT * FROM users WHERE email=%s", (email,))
                user = cur.fetchone()
                if user and bcrypt.check_password_hash(user[4], password):
                    session['user'] = user[1]
                    return redirect(url_for('dashboard'))
                else:
                    flash("Invalid email or password", "red")
            finally:
                conn.close()

    return render_template_string(
        form_template, title="Login", fields=fields, button="Login",
        extra_link={"url": url_for('register'), "text": "No account? Register"}
    )

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash("Login first", "red")
        return redirect(url_for('login'))
    return render_template_string(dashboard_template)

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "green")
    return redirect(url_for('login'))

# ---------------- Owner route: print users in terminal ----------------
@app.route('/print_users')
def print_users():
    secret = request.args.get('secret')
    if secret != OWNER_DOWNLOAD_KEY:
        return "Access denied!", 403

    conn = connect_to_db()
    if not conn:
        return "Database connection error!", 500

    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, dob, email FROM users")
        users = cur.fetchall()
        print("\n----- All Users -----")
        for u in users:
            print(f"ID: {u[0]}, Name: {u[1]}, DOB: {u[2]}, Email: {u[3]}")
        print("--------------------\n")
        return "Users printed in server terminal successfully!"
    finally:
        conn.close()

# ---------------- Owner route: delete all users ----------------
@app.route('/delete_users')
def delete_users():
    secret = request.args.get('secret')
    if secret != OWNER_DOWNLOAD_KEY:
        return "Access denied!", 403

    conn = connect_to_db()
    if not conn:
        return "Database connection error!", 500

    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users")
        conn.commit()
        return "All users deleted successfully!"
    finally:
        conn.close()

# ---------------- Run App ----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
