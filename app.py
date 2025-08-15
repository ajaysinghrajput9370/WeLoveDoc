import os
import uuid
import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
from werkzeug.utils import secure_filename

from config import Config
from database import init_db
from file_manager import (
    create_user, get_user_by_email, verify_password,
    record_task, get_task_count, active_subscription,
    start_subscription, add_device_if_allowed
)
from highlight_feature import load_ids_from_excel, highlight_pdf_by_ids, save_unmatched_to_excel

import razorpay

app = Flask(__name__)
app.config.from_object(Config)

# Ensure folders exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["RESULT_FOLDER"], exist_ok=True)

# Initialize DB
init_db()

# Razorpay client placeholder (works when keys set in env)
razor_client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))

def session_id():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    return session["sid"]

@app.context_processor
def inject_config():
    return dict(config=Config)

@app.route("/")
def index():
    user_id = session.get("user_id")
    sub = active_subscription(user_id) if user_id else None
    free_used = get_task_count(user_id=user_id) if user_id else get_task_count(session_id=session_id())
    return render_template("index.html",
                           subscription=sub,
                           free_used=free_used,
                           free_limit=Config.FREE_TASKS_PER_MONTH)

@app.route("/process", methods=["POST"])
def process_files():
    # Enforce free limit if no active subscription
    user_id = session.get("user_id")
    sub = active_subscription(user_id) if user_id else None
    if not sub:
        used = get_task_count(user_id=user_id) if user_id else get_task_count(session_id=session_id())
        if used >= Config.FREE_TASKS_PER_MONTH:
            flash("Free task limit reached. Please subscribe to continue.", "warning")
            return redirect(url_for("subscribe"))

    pdf = request.files.get("pdf")
    excel = request.files.get("excel")
    if not pdf or not excel:
        flash("Please upload both PDF and Excel.", "danger")
        return redirect(url_for("index"))

    pdf_filename = secure_filename(pdf.filename)
    excel_filename = secure_filename(excel.filename)
    pdf_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{uuid.uuid4()}_{pdf_filename}")
    excel_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{uuid.uuid4()}_{excel_filename}")
    pdf.save(pdf_path)
    excel.save(excel_path)

    # Load IDs and run highlighter
    ids = load_ids_from_excel(excel_path)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_pdf_path = os.path.join(app.config["RESULT_FOLDER"], f"ecr_result_{ts}.pdf")
    matched_pages, marks = highlight_pdf_by_ids(pdf_path, ids, out_pdf_path)

    out_excel_path = os.path.join(app.config["RESULT_FOLDER"], f"Data_Not_Found_{ts}.xlsx")
    save_unmatched_to_excel(ids, matched_pages, excel_path, out_excel_path)

    # Record usage
    if sub:
        record_task(user_id=user_id)
    else:
        record_task(session_id=session_id())

    return render_template("results.html",
                           pdf_file=os.path.basename(out_pdf_path),
                           excel_file=os.path.basename(out_excel_path),
                           matched_pages=matched_pages,
                           marks=marks)

# ---------- Auth ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        row = get_user_by_email(email)
        if not row or not verify_password(row, password):
            flash("Invalid credentials", "danger")
            return redirect(url_for("login"))
        session["user_id"] = row["id"]
        fp = request.form.get("fingerprint")
        if fp:
            add_device_if_allowed(row["id"], fp)
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not (name and email and password):
            flash("All fields required", "danger")
            return redirect(url_for("register"))
        try:
            uid = create_user(name, email, password)
        except Exception:
            flash("Email already registered", "danger")
            return redirect(url_for("register"))
        session["user_id"] = uid
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    uid = session["user_id"]
    sub = active_subscription(uid)
    free_used = get_task_count(user_id=uid)
    return render_template("dashboard.html", subscription=sub, free_used=free_used, free_limit=Config.FREE_TASKS_PER_MONTH)

# ---------- Subscription & Razorpay ----------
@app.route("/subscribe")
def subscribe():
    uid = session.get("user_id")
    sub = active_subscription(uid) if uid else None
    return render_template("subscribe.html", subscription=sub)

@app.route("/create_order", methods=["POST"])
def create_order():
    plan = request.form.get("plan")  # monthly, 6month, 12month
    amount = {
        "monthly": Config.PLAN_MONTHLY,
        "6month": Config.PLAN_6MONTH,
        "12month": Config.PLAN_12MONTH
    }[plan] * 100  # rupees -> paise
    order = razor_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })
    return order

@app.route("/payment_success", methods=["POST"])
def payment_success():
    # NOTE: validate signature in production
    uid = session.get("user_id")
    plan = request.form.get("plan")
    if not uid:
        flash("Login required to activate subscription.", "danger")
        return redirect(url_for("login"))
    start_subscription(uid, plan)
    flash("Subscription activated!", "success")
    return redirect(url_for("dashboard"))

# ---------- Download ----------
@app.route("/download/<kind>/<filename>")
def download(kind, filename):
    folder = app.config["RESULT_FOLDER"] if kind == "result" else app.config["UPLOAD_FOLDER"]
    file_path = os.path.join(folder, filename)
    if not os.path.exists(file_path):
        flash("File not found", "danger")
        return redirect(url_for("index"))
    return send_file(file_path, as_attachment=True)

@app.errorhandler(413)
def too_large(e):
    return render_template("error.html", message="File too large (max 50MB)."), 413

if __name__ == "__main__":
    app.run(debug=True)
