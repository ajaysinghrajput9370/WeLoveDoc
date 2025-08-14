from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from highlight import process_files  # Tumhara existing highlight logic

app = Flask(__name__)
app.secret_key = "sOUMU"

UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# ------------------ DB Setup ------------------
def get_db_connection():
    conn = sqlite3.connect("users.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                subscription_expiry TEXT
            )
        """)
    print("Database ready!")

init_db()

# ------------------ Routes ------------------
@app.route("/")
def index():
    username = session.get("username")
    is_subscribed = False
    sub_expiry_date = None

    if username:
        with get_db_connection() as conn:
            row = conn.execute("SELECT subscription_expiry FROM users WHERE username=?", (username,)).fetchone()
            if row and row["subscription_expiry"]:
                sub_expiry_date = row["subscription_expiry"]
                is_subscribed = True

    return render_template("index.html", user=username, is_subscribed=is_subscribed, sub_expiry_date=sub_expiry_date)

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
            with get_db_connection() as conn:
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

        with get_db_connection() as conn:
            row = conn.execute("SELECT password FROM users WHERE username=?", (username,)).fetchone()

        if row and check_password_hash(row["password"], password):
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

# ------------------ Static Info Pages ------------------
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/plans")
def plans():
    return render_template("plans.html")

# Dummy pages for footer links
@app.route("/refund")
def refund(): return render_template("refund.html")
@app.route("/shipping")
def shipping(): return render_template("shipping.html")
@app.route("/contact")
def contact(): return render_template("contact.html")

# ------------------ File Highlight Route ------------------
@app.route("/highlight", methods=["POST"])
def highlight_route():
    if "username" not in session:
        flash("Please log in to use this feature", "warning")
        return redirect(url_for("login"))

    pdf_file = request.files.get("pdf_file")
    excel_file = request.files.get("excel_file")
    highlight_type = request.form.get("highlight_type", "uan")

    if not pdf_file or not excel_file:
        flash("Please upload both PDF and Excel files", "danger")
        return redirect(url_for("index"))

    pdf_path = os.path.join(UPLOAD_FOLDER, secure_filename(pdf_file.filename))
    excel_path = os.path.join(UPLOAD_FOLDER, secure_filename(excel_file.filename))

    pdf_file.save(pdf_path)
    excel_file.save(excel_path)

    try:
        result_pdf, result_excel = process_files(pdf_path, excel_path, RESULT_FOLDER, highlight_type)
    except Exception as e:
        flash(f"Error processing files: {e}", "danger")
        return redirect(url_for("index"))

    flash("Files processed successfully!", "success")
    return send_file(result_pdf, as_attachment=True)

# ------------------ Run App ------------------
if __name__ == "__main__":
    app.run(debug=True)
