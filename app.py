import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from urllib.parse import urlparse

app = Flask(__name__)


# Get database URL from environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')

# Owner credentials (for owner login and dashboard access)
OWNER_EMAIL = os.environ.get('OWNER_EMAIL', 'owner@example.com')
OWNER_PASS = os.environ.get('OWNER_PASS', 'ownerpassword')

def get_db_connection():
    # Parse the database URL because psycopg2 requires components separately
    result = urlparse(DATABASE_URL)
    username = result.username
    password = result.password
    database = result.path[1:]
    hostname = result.hostname
    port = result.port
    conn = psycopg2.connect(
        database=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    return conn

def create_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            dob DATE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

create_table()

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        name = request.form['name']
        dob = request.form['dob']
        email = request.form['email']
        password = request.form['password']
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (name, dob, email, password) VALUES (%s, %s, %s, %s)",
                        (name, dob, email, password))
            conn.commit()
            cur.close()
            conn.close()
            return redirect('/login')
        except Exception:
            msg = "Registration failed. Email may already exist."
    return '''
        <form method="post">
            Name: <input name="name" required><br>
            DOB: <input name="dob" type="date" required><br>
            Email: <input name="email" type="email" required><br>
            Password: <input name="password" type="password" required><br>
            <button type="submit">Register</button>
        </form>
        <p>{}</p>
        <a href="/login">Login</a>
    '''.format(msg)

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email == OWNER_EMAIL and password == OWNER_PASS:
            session['owner'] = True
            return redirect(url_for('dashboard'))
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s AND password=%s", (email, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            session['user'] = user[0]
            return "Login successful! <a href='/logout'>Logout</a>"
        else:
            msg = "Incorrect credentials."
    return '''
        <form method="post">
            Email: <input name="email" type="email" required><br>
            Password: <input name="password" type="password" required><br>
            <button type="submit">Login</button>
        </form>
        <p>{}</p>
        <a href="/register">Register</a>
    '''.format(msg)

@app.route('/dashboard')
def dashboard():
    if not session.get('owner'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, dob, email FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    user_list = '<ul>' + ''.join(['<li>{} | {} | {}</li>'.format(u[0], u[1], u[2]) for u in users]) + '</ul>'
    return '''
        <h2>Registered Users</h2>
        {}
        <a href="/logout">Logout</a>
    '''.format(user_list)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=False)  # For production, disable debug modebug=True)
