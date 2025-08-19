import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader, PdfWriter
import pandas as pd

# ---------------- Flask App ----------------
app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------------- DB Setup ----------------
DB_NAME = "users.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            is_subscribed INTEGER DEFAULT 0
        )
        """)
    print("✅ Database initialized")

init_db()

# ---------------- User System ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return redirect(url_for("signup"))
        hashed_pw = generate_password_hash(password)
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_pw))
                conn.commit()
            session["user"] = email
            flash("Signup successful! You are now logged in.", "success")
            return redirect(url_for("home"))
        except sqlite3.IntegrityError:
            with sqlite3.connect(DB_NAME) as conn:
                cur = conn.cursor()
                cur.execute("SELECT password FROM users WHERE email=?", (email,))
                row = cur.fetchone()
            if row and check_password_hash(row[0], password):
                session["user"] = email
                flash("Logged in successfully!", "success")
                return redirect(url_for("home"))
            else:
                flash("Email already exists with different password!", "danger")
                return redirect(url_for("signup"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return redirect(url_for("login"))
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("SELECT password FROM users WHERE email=?", (email,))
            row = cur.fetchone()
        if row and check_password_hash(row[0], password):
            session["user"] = email
            flash("Login successful!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials!", "danger")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

# ---------------- Home ----------------
@app.route("/")
@app.route("/home")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT is_subscribed FROM users WHERE email=?", (session["user"],))
        row = cur.fetchone()
        subscribed = bool(row[0]) if row else False

    return render_template("home.html", username=session["user"], subscribed=subscribed)

# ---------------- Subscription Activation ----------------
@app.route("/activate")
def activate():
    if "user" not in session:
        return redirect(url_for("login"))
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_subscribed=1 WHERE email=?", (session["user"],))
        conn.commit()
    flash("Subscription activated! You can now use the highlight tool.", "success")
    return redirect(url_for("home"))

# ---------------- Upload & Highlight ----------------
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

@app.route("/highlight", methods=["GET", "POST"])
def highlight():
    if "user" not in session:
        return redirect(url_for("login"))

    # Check subscription
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT is_subscribed FROM users WHERE email=?", (session["user"],))
        row = cur.fetchone()
        if not row or row[0] == 0:
            flash("You need a subscription to highlight PDFs.", "warning")
            return redirect(url_for("subscribe_popup"))

    if request.method == "POST":
        pdf_file = request.files.get("pdf")
        excel_file = request.files.get("excel")
        if not pdf_file or not excel_file:
            flash("Please upload both PDF and Excel.", "danger")
            return redirect(request.url)

        pdf_path = os.path.join(UPLOAD_FOLDER, pdf_file.filename)
        excel_path = os.path.join(UPLOAD_FOLDER, excel_file.filename)
        pdf_file.save(pdf_path)
        excel_file.save(excel_path)

        result_pdf, result_excel = process_files(pdf_path, excel_path)

        flash("Files processed successfully!", "success")
        return render_template("result.html", pdf_file=result_pdf, excel_file=result_excel)

    return render_template("highlight.html")

# ---------------- Highlight Processing ----------------
def process_files(pdf_path, excel_path, highlight_type="uan"):
    os.makedirs(RESULTS_FOLDER, exist_ok=True)

    # Read Excel
    df = pd.read_excel(excel_path)
    highlight_values = df[highlight_type].astype(str).tolist()

    # Read PDF
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    unmatched = []

    for page in reader.pages:
        text = page.extract_text() or ""
        found_any = False
        for value in highlight_values:
            if value in text:
                try:
                    page.add_highlight_annotation([50, 750, 200, 770])
                except Exception:
                    pass
                found_any = True
        if not found_any:
            unmatched.extend(highlight_values)
        writer.add_page(page)

    result_pdf_path = os.path.join(RESULTS_FOLDER, "highlighted.pdf")
    with open(result_pdf_path, "wb") as f:
        writer.write(f)

    result_excel_path = os.path.join(RESULTS_FOLDER, "unmatched.xlsx")
    pd.DataFrame(unmatched, columns=[highlight_type]).to_excel(result_excel_path, index=False)

    return "highlighted.pdf", "unmatched.xlsx"

# ---------------- Download ----------------
@app.route("/results/<filename>")
def download(filename):
    return send_from_directory(RESULTS_FOLDER, filename)

# ---------------- Subscription Popup ----------------
@app.route("/subscribe_popup")
def subscribe_popup():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("subscribe_popup.html")

# ---------------- Run App ----------------
if __name__ == "__main__":
    app.run(debug=True)
