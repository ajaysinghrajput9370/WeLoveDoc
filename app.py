from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from highlight import process_files  # tumhara existing highlight logic

app = Flask(__name__)
app.secret_key = "sOUMU"

UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# ------------------ Database Setup ------------------
def init_db():
    with sqlite3.connect("users.db") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
    print("Database ready!")

init_db()

# ------------------ Routes ------------------
@app.route("/")
def index():
    return render_template("index.html", username=session.get("username"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            flash("Please fill all fields", "danger")
            return redirect(url_for("signup"))

        hashed_pw = generate_password_hash(password)
        try:
            with sqlite3.connect("users.db") as conn:
                conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already taken", "danger")
            return redirect(url_for("signup"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        with sqlite3.connect("users.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT password FROM users WHERE username=?", (username,))
            row = cur.fetchone()

        if row and check_password_hash(row[0], password):
            session["username"] = username
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("Logged out successfully", "info")
    return redirect(url_for("index"))

@app.route("/plans")
def plans():
    return render_template("plans.html")

@app.route("/upload", methods=["POST"])
def upload():
    if "username" not in session:
        flash("Please log in to use this feature", "warning")
        return redirect(url_for("login"))

    pdf_file = request.files.get("pdf_file")
    excel_file = request.files.get("excel_file")

    if not pdf_file or not excel_file:
        flash("Please upload both PDF and Excel files", "danger")
        return redirect(url_for("index"))

    pdf_path = os.path.join(UPLOAD_FOLDER, secure_filename(pdf_file.filename))
    excel_path = os.path.join(UPLOAD_FOLDER, secure_filename(excel_file.filename))

    pdf_file.save(pdf_path)
    excel_file.save(excel_path)

    result_pdf, result_excel = process_files(pdf_path, excel_path, RESULT_FOLDER)

    flash("Files processed successfully!", "success")
    return send_file(result_pdf, as_attachment=True)

# ------------------ Run App ------------------
if __name__ == "__main__":
    app.run(debug=True)
