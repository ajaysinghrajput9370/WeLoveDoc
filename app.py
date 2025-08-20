import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader, PdfWriter
import pandas as pd

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_NAME = "users.db"

# ---------------- DATABASE INIT ----------------
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
    print("Database initialized")

init_db()

# ---------------- AUTH ROUTES ----------------
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method=="POST":
        email=request.form["email"]
        password=request.form["password"]
        hashed=generate_password_hash(password)
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("INSERT INTO users(email,password) VALUES(?,?)",(email,hashed))
            session["user"]=email
            flash("Signup successful!","success")
            return redirect(url_for("home"))
        except sqlite3.IntegrityError:
            flash("Email already exists!","danger")
            return redirect(url_for("signup"))
    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form["email"]
        password=request.form["password"]
        with sqlite3.connect(DB_NAME) as conn:
            cur=conn.cursor()
            cur.execute("SELECT password FROM users WHERE email=?",(email,))
            row=cur.fetchone()
        if row and check_password_hash(row[0],password):
            session["user"]=email
            flash("Login successful","success")
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials","danger")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user",None)
    flash("Logged out","info")
    return redirect(url_for("login"))

# ---------------- HOME ----------------
@app.route("/")
@app.route("/home")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    with sqlite3.connect(DB_NAME) as conn:
        cur=conn.cursor()
        cur.execute("SELECT is_subscribed FROM users WHERE email=?",(session["user"],))
        row=cur.fetchone()
        subscribed=bool(row[0]) if row else False
    return render_template("home.html", username=session["user"], subscribed=subscribed)

# ---------------- ACTIVATE ----------------
@app.route("/activate")
def activate():
    if "user" not in session:
        return redirect(url_for("login"))
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE users SET is_subscribed=1 WHERE email=?",(session["user"],))
        conn.commit()
    flash("Subscription activated!","success")
    return redirect(url_for("home"))

# ---------------- FILE UPLOADS ----------------
UPLOAD_FOLDER="uploads"
RESULTS_FOLDER="results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

@app.route("/highlight", methods=["GET","POST"])
def highlight():
    if "user" not in session:
        return redirect(url_for("login"))
    with sqlite3.connect(DB_NAME) as conn:
        cur=conn.cursor()
        cur.execute("SELECT is_subscribed FROM users WHERE email=?",(session["user"],))
        row=cur.fetchone()
        if not row or row[0]==0:
            flash("Subscription required","warning")
            return redirect(url_for("home"))   # change to popup if you want
    
    if request.method=="POST":
        pdf_file=request.files.get("pdf")
        excel_file=request.files.get("excel")
        if not pdf_file or not excel_file:
            flash("Upload both files","danger")
            return redirect(request.url)

        pdf_path=os.path.join(UPLOAD_FOLDER,pdf_file.filename)
        excel_path=os.path.join(UPLOAD_FOLDER,excel_file.filename)
        pdf_file.save(pdf_path)
        excel_file.save(excel_path)

        result_pdf, result_excel = process_files(pdf_path,excel_path)
        flash("Highlight done!","success")
        return render_template("result.html", pdf_file=result_pdf, excel_file=result_excel)

    return render_template("highlight.html")

# ---------------- PROCESS FILES ----------------
def process_files(pdf_path, excel_path, highlight_type="uan"):
    df=pd.read_excel(excel_path)
    values=df[highlight_type].astype(str).tolist()

    reader=PdfReader(pdf_path)
    writer=PdfWriter()
    unmatched=[]

    for page in reader.pages:
        text=page.extract_text() or ""
        found=False
        for val in values:
            if val in text:
                try:
                    page.add_highlight_annotation([50,750,200,770])
                except: 
                    pass
                found=True
        if not found:
            unmatched.extend(values)
        writer.add_page(page)

    result_pdf=os.path.join(RESULTS_FOLDER,"highlighted.pdf")
    with open(result_pdf,"wb") as f:
        writer.write(f)

    result_excel=os.path.join(RESULTS_FOLDER,"unmatched.xlsx")
    pd.DataFrame({"unmatched": unmatched}).to_excel(result_excel, index=False)

    return result_pdf, result_excel


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
