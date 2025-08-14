import os
import time
import sqlite3
import datetime
from datetime import timedelta

from flask import (
    Flask,
    render_template,
    request,
    send_file,
    redirect,
    url_for,
    session,
    flash,
    abort,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Optional Razorpay (guarded if keys not present)
try:
    import razorpay
except Exception:  # pragma: no cover
    razorpay = None

# ---- Your PDF highlight function ----
# Must return (out_pdf_path, not_found_excel_path)
from highlight import process_files

# ----------------------------------------------------------------------------
# App setup
# ----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "very_secure_random_string")
app.permanent_session_lifetime = timedelta(days=30)  # user stays logged in until logout

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static"), exist_ok=True)

# ----------------------------------------------------------------------------
# Razorpay (safe init)
# ----------------------------------------------------------------------------
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
razorpay_client = None
if razorpay and RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    except Exception:
        razorpay_client = None

# ----------------------------------------------------------------------------
# Database helpers
# ----------------------------------------------------------------------------
DB_PATH = os.path.join(BASE_DIR, "users.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            tasks_done INTEGER DEFAULT 0,
            subscription_expiry INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


# ----------------------------------------------------------------------------
# File helpers
# ----------------------------------------------------------------------------

def clean_old_uploads(folder: str, max_age_minutes: int = 30) -> None:
    now = time.time()
    max_age = max_age_minutes * 60
    for filename in os.listdir(folder):
        fp = os.path.join(folder, filename)
        try:
            if os.path.isfile(fp) and now - os.path.getmtime(fp) > max_age:
                os.remove(fp)
        except Exception:
            pass


def save_uploaded_file(file_storage):
    filename = secure_filename(file_storage.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file_storage.save(path)
    return filename, path


# ----------------------------------------------------------------------------
# Auth: Email + Password (no OTP)
# ----------------------------------------------------------------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        name = (request.form.get("name") or "").strip()
        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("signup.html")
        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO users (email, password, name) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), name),
            )
            conn.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email is already registered.", "danger")
        finally:
            conn.close()
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        conn = get_db_connection()
        user = conn.execute(
            "SELECT id, password, name FROM users WHERE email=?", (email,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session.permanent = True
            session["user_id"] = user["id"]
            session["email"] = email
            session["user_name"] = user["name"]
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ----------------------------------------------------------------------------
# Plans & Payments (Razorpay)
# ----------------------------------------------------------------------------

@app.route("/plans")
def plans():
    return render_template("plans.html")


@app.route("/create_order", methods=["POST"])
def create_order():
    if not razorpay_client:
        flash("Payment is temporarily unavailable. Contact support.", "danger")
        return redirect(url_for("plans"))
    try:
        amount_rupees = int(request.form.get("amount"))
    except Exception:
        flash("Invalid amount.", "danger")
        return redirect(url_for("plans"))

    amount_paise = amount_rupees * 100
    receipt = f"order_rcptid_{int(time.time())}"
    order = razorpay_client.order.create(
        dict(amount=amount_paise, currency="INR", receipt=receipt, payment_capture="1")
    )
    return render_template(
        "payment.html",
        razorpay_order_id=order["id"],
        razorpay_merchant_key=RAZORPAY_KEY_ID,
        amount=amount_paise,
        currency="INR",
        user_email=session.get("email", ""),
    )


@app.route("/payment_success", methods=["POST"])
def payment_success():
    if not razorpay_client:
        flash("Payment verification unavailable.", "danger")
        return redirect(url_for("plans"))
    payment_id = request.form.get("razorpay_payment_id")
    order_id = request.form.get("razorpay_order_id")
    signature = request.form.get("razorpay_signature")
    try:
        razorpay_client.utility.verify_payment_signature(
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
        )
        # Set subscription = 30 days from now
        now = int(time.time())
        expiry = now + 30 * 24 * 3600
        conn = get_db_connection()
        conn.execute(
            "UPDATE users SET subscription_expiry=? WHERE email=?",
            (expiry, session.get("email")),
        )
        conn.commit()
        conn.close()
        flash("Payment successful! Subscription activated.", "success")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Payment verification failed: {e}", "danger")
        return redirect(url_for("plans"))


# ----------------------------------------------------------------------------
# Index / Dashboard
# ----------------------------------------------------------------------------

@app.route("/")
def index():
    user_email = None
    is_subscribed = False
    tasks_done = 0

    if "user_id" in session:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT email, tasks_done, subscription_expiry FROM users WHERE id=?",
            (session["user_id"],),
        ).fetchone()
        conn.close()
        if row:
            user_email = row["email"]
            tasks_done = row["tasks_done"] or 0
            sub_expiry = row["subscription_expiry"]
            now = int(time.time())
            is_subscribed = bool(sub_expiry and sub_expiry > now)

    return render_template(
        "index.html", user=user_email, is_subscribed=is_subscribed, tasks_done=tasks_done
    )


# ----------------------------------------------------------------------------
# Highlight route (free: 2 tasks unless subscribed)
# ----------------------------------------------------------------------------

@app.route("/highlight", methods=["POST"])
def highlight_route():
    if "user_id" not in session:
        return (
            """
            <h3>Please login to use this feature.</h3>
            <a href='/login'>Login</a> | <a href='/signup'>Signup</a>
            """,
            403,
        )

    # Check quota / subscription
    conn = get_db_connection()
    row = conn.execute(
        "SELECT tasks_done, subscription_expiry FROM users WHERE id=?",
        (session["user_id"],),
    ).fetchone()
    conn.close()

    now = int(time.time())
    tasks_done = row["tasks_done"] if row else 0
    sub_expiry = row["subscription_expiry"] if row else None
    is_subscribed = bool(sub_expiry and sub_expiry > now)

    if not is_subscribed and tasks_done >= 2:
        return (
            """
            <html><body style="font-family:Arial;text-align:center;padding:40px;background:#f9f9f9">
              <div style="display:inline-block;background:#fff;padding:30px;border-radius:12px;box-shadow:0 0 15px rgba(0,0,0,0.1)">
                <h3 style="color:#d32f2f">Free task limit reached (2/2)</h3>
                <p>Please subscribe to continue.</p>
                <a href="/plans" style="background:#1976d2;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none">View Plans</a>
              </div>
            </body></html>
            """,
            403,
        )

    clean_old_uploads(UPLOAD_FOLDER)

    pdf_file = request.files.get("pdf_file")
    excel_file = request.files.get("excel_file")
    highlight_type = request.form.get("highlight_type")  # 'uan' or 'esic'

    if not pdf_file or not excel_file or highlight_type not in {"uan", "esic"}:
        flash("Please upload both PDF and Excel, and select UAN or ESIC.", "danger")
        return redirect(url_for("index"))

    _pdf_name, pdf_path = save_uploaded_file(pdf_file)
    _excel_name, excel_path = save_uploaded_file(excel_file)

    # Process
    out_pdf_path, not_found_excel_path = process_files(
        pdf_path=pdf_path,
        excel_path=excel_path,
        mode=highlight_type,
        output_dir=UPLOAD_FOLDER,
    )

    # Increment task count
    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET tasks_done = COALESCE(tasks_done, 0) + 1 WHERE id=?",
        (session["user_id"],),
    )
    conn.commit()
    conn.close()

    # Show result with safe filenames for downloads
    out_pdf_filename = os.path.basename(out_pdf_path) if out_pdf_path else None
    not_found_excel_filename = os.path.basename(not_found_excel_path) if not_found_excel_path else None

    return render_template(
        "result.html",
        out_pdf=out_pdf_filename,
        not_found_excel=not_found_excel_filename,
    )


# ----------------------------------------------------------------------------
# Safe download routes (only from UPLOAD_FOLDER)
# ----------------------------------------------------------------------------

@app.route("/download_pdf")
def download_pdf():
    filename = request.args.get("file")
    if not filename:
        abort(404)
    path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
    if not (os.path.exists(path) and os.path.isfile(path)):
        abort(404)
    return send_file(path, as_attachment=True)


@app.route("/download_excel")
def download_excel():
    filename = request.args.get("file")
    if not filename:
        abort(404)
    path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
    if not (os.path.exists(path) and os.path.isfile(path)):
        abort(404)
    return send_file(path, as_attachment=True)


# ----------------------------------------------------------------------------
# Static pages
# ----------------------------------------------------------------------------

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/refunds")
def refunds():
    return render_template("refunds.html")


@app.route("/shipping")
def shipping():
    return render_template("shipping.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route('/sitemap.xml')
def sitemap():
    lastmod = datetime.date.today().isoformat()
    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://welovedoc.in/</loc>
        <lastmod>{lastmod}</lastmod>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
      </url>
    </urlset>"""
    return sitemap_xml, 200, {'Content-Type': 'application/xml'}


# ----------------------------------------------------------------------------
# Bootstrap
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
