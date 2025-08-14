import os
import time
import sqlite3
from datetime import timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Try import razorpay if installed; otherwise leave None
try:
    import razorpay
except Exception:
    razorpay = None

# Use your existing highlight.py (unchanged)
try:
    from highlight import process_files
except Exception:
    process_files = None

# App config
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change_this_in_production")
app.permanent_session_lifetime = timedelta(days=365)  # session stays until logout

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(BASE_DIR, "users.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Razorpay keys from env (optional)
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
razorpay_client = None
if razorpay and RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    except Exception:
        razorpay_client = None

# ---------- Database helpers ----------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      name TEXT,
      tasks_done INTEGER DEFAULT 0,
      subscription_expiry INTEGER,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS payments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      plan TEXT,
      amount INTEGER,
      razorpay_order_id TEXT,
      status TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

# ensure DB exists on import and first request
init_db()

@app.before_first_request
def _init_first():
    init_db()

# ---------- Utilities ----------
def clean_old_uploads(folder, max_age_minutes=60):
    now = time.time()
    max_age = max_age_minutes * 60
    for fn in os.listdir(folder):
        path = os.path.join(folder, fn)
        try:
            if os.path.isfile(path) and (now - os.path.getmtime(path) > max_age):
                os.remove(path)
        except Exception:
            pass

def save_uploaded_file(file_storage):
    name = secure_filename(file_storage.filename or f"upload_{int(time.time())}")
    base, ext = os.path.splitext(name)
    i = 1
    out = name
    while os.path.exists(os.path.join(UPLOAD_FOLDER, out)):
        i += 1
        out = f"{base}_{i}{ext}"
    path = os.path.join(UPLOAD_FOLDER, out)
    file_storage.save(path)
    return out, path

def is_subscribed(row):
    try:
        if not row:
            return False
        exp = row["subscription_expiry"]
        return bool(exp and int(exp) > int(time.time()))
    except Exception:
        return False

def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapper

@app.before_request
def keep_session_permanent():
    if "user_id" in session:
        session.permanent = True

# ---------- Routes: Auth ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        name = (request.form.get("name") or "").strip() or None
        if not email or not password:
            flash("Email and password required.", "danger")
            return render_template("signup.html")
        hashed = generate_password_hash(password)
        try:
            conn = get_db_connection()
            conn.execute("INSERT INTO users (email, password, name) VALUES (?, ?, ?)", (email, hashed, name))
            conn.commit()
            conn.close()
            flash("Account created. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")
        except Exception as e:
            flash(f"Error: {e}", "danger")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["user_name"] = user["name"]
            flash("Logged in successfully.", "success")
            return redirect(url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

# ---------- Index / Dashboard ----------
@app.route("/")
def index():
    user_email = None
    tasks_done = 0
    subscribed = False
    if "user_id" in session:
        conn = get_db_connection()
        row = conn.execute("SELECT email, tasks_done, subscription_expiry FROM users WHERE id=?", (session["user_id"],)).fetchone()
        conn.close()
        if row:
            user_email = row["email"]
            tasks_done = row["tasks_done"] or 0
            subscribed = is_subscribed(row)
    return render_template("index.html", user=user_email, tasks_done=tasks_done, is_subscribed=subscribed, razorpay_enabled=bool(razorpay_client))

# ---------- Highlight ----------
@app.route("/highlight", methods=["POST"])
@login_required
def highlight_route():
    if not process_files:
        flash("Highlight feature not configured on server.", "danger")
        return redirect(url_for("index"))

    conn = get_db_connection()
    row = conn.execute("SELECT tasks_done, subscription_expiry FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    subscribed = is_subscribed(row)
    tasks_done = (row["tasks_done"] or 0) if row else 0

    if (not subscribed) and tasks_done >= 2:
        return render_template("limit.html"), 403

    clean_old_uploads(UPLOAD_FOLDER)
    pdf_file = request.files.get("pdf_file")
    excel_file = request.files.get("excel_file")
    highlight_type = request.form.get("highlight_type")
    if not pdf_file or not excel_file or highlight_type not in {"uan", "esic"}:
        flash("Please upload PDF & Excel and select UAN/ESIC.", "danger")
        return redirect(url_for("index"))

    pdf_name, pdf_path = save_uploaded_file(pdf_file)
    excel_name, excel_path = save_uploaded_file(excel_file)

    out_pdf_path, not_found_excel_path = process_files(pdf_path=pdf_path, excel_path=excel_path, mode=highlight_type, output_dir=UPLOAD_FOLDER)

    # increment tasks_done
    conn = get_db_connection()
    conn.execute("UPDATE users SET tasks_done = COALESCE(tasks_done, 0) + 1 WHERE id=?", (session["user_id"],))
    conn.commit()
    conn.close()

    return render_template("result.html", out_pdf=os.path.basename(out_pdf_path) if out_pdf_path else None, not_found_excel=os.path.basename(not_found_excel_path) if not_found_excel_path else None)

# ---------- Downloads ----------
@app.route("/download_pdf")
@login_required
def download_pdf():
    filename = request.args.get("file", "")
    if not filename:
        abort(404)
    path = os.path.join(UPLOAD_FOLDER, os.path.basename(filename))
    if not (os.path.exists(path) and os.path.isfile(path)):
        abort(404)
    return send_file(path, as_attachment=True)

@app.route("/download_excel")
@login_required
def download_excel():
    filename = request.args.get("file", "")
    if not filename:
        abort(404)
    path = os.path.join(UPLOAD_FOLDER, os.path.basename(filename))
    if not (os.path.exists(path) and os.path.isfile(path)):
        abort(404)
    return send_file(path, as_attachment=True)

# ---------- Plans & Razorpay ----------
@app.route("/plans")
@login_required
def plans():
    return render_template("plans.html", razorpay_enabled=bool(razorpay_client))

@app.route("/create_order", methods=["POST"])
@login_required
def create_order():
    if not razorpay_client:
        flash("Payment gateway not configured.", "danger")
        return redirect(url_for("plans"))
    try:
        amount_rupees = int(request.form.get("amount", "0"))
    except ValueError:
        amount_rupees = 0
    if amount_rupees <= 0:
        flash("Invalid amount.", "danger")
        return redirect(url_for("plans"))

    amount_paise = amount_rupees * 100
    receipt = f"rcpt_{int(time.time())}_{session['user_id']}"
    order = razorpay_client.order.create(dict(amount=amount_paise, currency="INR", receipt=receipt, payment_capture='1'))

    # store payment record
    conn = get_db_connection()
    conn.execute("INSERT INTO payments (user_id, plan, amount, razorpay_order_id, status) VALUES (?, ?, ?, ?, ?)",
                 (session["user_id"], request.form.get("plan", "monthly"), amount_paise, order["id"], "created"))
    conn.commit()
    conn.close()

    return render_template("payment.html", razorpay_merchant_key=RAZORPAY_KEY_ID, razorpay_order_id=order["id"], amount=amount_paise, currency="INR", user_email=session.get("email", ""))

@app.route("/payment_success", methods=["POST"])
@login_required
def payment_success():
    if not razorpay_client:
        flash("Payment gateway not configured.", "danger")
        return redirect(url_for("plans"))

    payment_id = request.form.get("razorpay_payment_id")
    order_id = request.form.get("razorpay_order_id")
    signature = request.form.get("razorpay_signature")

    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        expiry = int(time.time()) + 30 * 24 * 3600
        conn = get_db_connection()
        conn.execute("UPDATE users SET subscription_expiry=? WHERE id=?", (expiry, session["user_id"]))
        conn.execute("UPDATE payments SET status=?, razorpay_order_id=? WHERE razorpay_order_id=?", ("paid", order_id, order_id))
        conn.commit()
        conn.close()
        flash("Payment successful! Subscription activated for 30 days.", "success")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Payment verification failed: {e}", "danger")
        return redirect(url_for("plans"))

# ---------- Simple pages ----------
@app.route("/about")
def about():
    return render_template("page.html", title="About", content="About We ❤️ Doc")

@app.route("/contact")
def contact():
    return render_template("page.html", title="Contact", content="Contact: support@welovedoc.in")

@app.route("/privacy")
def privacy():
    return render_template("page.html", title="Privacy Policy", content="Privacy details...")

@app.route("/terms")
def terms():
    return render_template("page.html", title="Terms", content="Terms of service...")

@app.route("/favicon.ico")
def favicon():
    fpath = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(fpath):
        return send_file(fpath)
    abort(404)

@app.route("/sitemap.xml")
def sitemap():
    lastmod = time.strftime("%Y-%m-%d")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://welovedoc.in/</loc><lastmod>{lastmod}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>
</urlset>"""
    return xml, 200, {"Content-Type": "application/xml"}

# ---------- Run ----------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
