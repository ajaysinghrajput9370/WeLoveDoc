from flask import Flask, render_template, request, send_file, redirect, url_for, flash, session, jsonify
import os
import warnings
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import uuid
from datetime import datetime
from functools import wraps
from highlight_feature import highlight_pdf
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ignore razorpay warnings if any
warnings.filterwarnings("ignore", category=UserWarning)

# Flask app setup
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# File storage folders
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)


# ---------------------- DB Helper Functions ----------------------
def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Run this once to create DB schema if not exists."""
    with get_db_connection() as conn:
        with open("schema.sql") as f:
            conn.executescript(f.read())


def clear_uploads():
    """Remove all uploaded and result files"""
    for folder in [UPLOAD_FOLDER, RESULTS_FOLDER]:
        for f in os.listdir(folder):
            os.remove(os.path.join(folder, f))


# ---------------------- Decorators ----------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------- Routes ----------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        device_id = str(uuid.uuid4())

        conn = get_db_connection()
        try:
            password_hash = generate_password_hash(password)
            conn.execute(
                "INSERT INTO users (email, password_hash, device_id, subscription_active) VALUES (?, ?, ?, 0)",
                (email, password_hash, device_id)
            )
            conn.commit()
            user_id = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
            session["user_id"] = user_id
            session["device_id"] = device_id
            flash("Signup successful! You can now use the highlight feature.")
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            flash("Email already registered.")
        finally:
            conn.close()
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["device_id"] = user["device_id"]
            flash("Login successful!")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/highlight", methods=["GET", "POST"])
@login_required
def highlight():
    return render_template("highlight.html")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    output_pdf = None
    not_found_excel = None

    conn = get_db_connection()
    user = conn.execute("SELECT email FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    username = user["email"] if user else "User"

    if request.method == "POST":
        if request.form.get("action") == "refresh":
            clear_uploads()
            flash("Uploads and results cleared. Ready for new task.")
            return redirect(url_for("index"))

        clear_uploads()
        pdf_file = request.files.get("pdf")
        excel_file = request.files.get("excel")
        highlight_type = request.form.get("highlight_type")

        if not pdf_file or not excel_file:
            flash("Both PDF and Excel are required.")
            return redirect(request.url)

        pdf_path = os.path.join(UPLOAD_FOLDER, secure_filename(pdf_file.filename))
        excel_path = os.path.join(UPLOAD_FOLDER, secure_filename(excel_file.filename))
        pdf_file.save(pdf_path)
        excel_file.save(excel_path)

        output_pdf, not_found_excel = highlight_pdf(pdf_path, excel_path, highlight_type, RESULTS_FOLDER)

    return render_template("index.html", output_pdf=output_pdf, not_found_excel=not_found_excel, username=username)


@app.route("/download/<filename>")
def download_file(filename):
    return send_file(os.path.join(RESULTS_FOLDER, filename), as_attachment=True)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
