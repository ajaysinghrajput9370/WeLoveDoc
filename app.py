from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "YOUR_SECRET_KEY"  # Change this
app.permanent_session_lifetime = timedelta(days=30)  # 30 days session

def get_db():
    return sqlite3.connect("database.db")

@app.route("/")
def home():
    if "user" in session:
        return render_template("dashboard.html", email=session["user"])
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        conn.close()

        if row and check_password_hash(row[0], password):
            session.permanent = True
            session["user"] = email
            flash("Logged in successfully", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid email or password", "danger")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]

        hashed_pw = generate_password_hash(password)

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_pw))
            conn.commit()
            conn.close()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists", "danger")

    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)

