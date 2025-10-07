import os
from flask import Flask, render_template_string, request, redirect, session, url_for
import psycopg2
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_default_secret_key')

# Database URL and Owner credentials from environment variables
DATABASE_URL = os.environ.get('DATABASE_URL')
OWNER_EMAIL = os.environ.get('OWNER_EMAIL', 'owner@example.com')
OWNER_PASS = os.environ.get('OWNER_PASS', 'ownerpassword')

def get_db_connection():
    result = urlparse(DATABASE_URL)
    return psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )

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

@app.route('/')
def home():
    # Redirect to login or user/owner dashboard if logged in
    if session.get('owner'):
        return redirect('/dashboard')
    elif session.get('user'):
        return redirect('/user')
    else:
        return redirect('/login')

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
    # Basic HTML form for registration
    return render_template_string('''
        <form method="post">
            Name: <input name="name" required><br>
            DOB: <input name="dob" type="date" required><br>
            Email: <input name="email" type="email" required><br>
            Password: <input name="password" type="password" required><br>
            <button type="submit">Register</button>
        </form>
        <p>{{ msg }}</p>
        <a href="/login">Login</a>
    ''', msg=msg)

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email == OWNER_EMAIL and password == OWNER_PASS:
            session.clear()
            session['owner'] = True
            return redirect('/dashboard')
        else:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email=%s AND password=%s", (email, password))
            user = cur.fetchone()
            cur.close()
            conn.close()
            if user:
                session.clear()
                session['user'] = user[0]
                return redirect('/user')
            else:
                msg = "Incorrect credentials."
    return render_template_string('''
        <form method="post">
            Email: <input name="email" type="email" required><br>
            Password: <input name="password" type="password" required><br>
            <button type="submit">Login</button>
        </form>
        <p>{{ msg }}</p>
        <a href="/register">Register</a>
    ''', msg=msg)

@app.route('/dashboard')
def dashboard():
    if not session.get('owner'):
        return redirect('/login')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, dob, email FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    users_html = '<ul>' + ''.join(f'<li>{u[0]} | {u[1]} | {u[2]}</li>' for u in users) + '</ul>'
    return f'''
        <h2>Owner Dashboard - Registered Users</h2>
        {users_html}
        <a href="/logout">Logout</a>
    '''

@app.route('/user')
def user_home():
    if not session.get('user'):
        return redirect('/login')
    return '''
        <h2>User Home Page</h2>
        <p>Welcome, user!</p>
        <a href="/logout">Logout</a>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=False)
