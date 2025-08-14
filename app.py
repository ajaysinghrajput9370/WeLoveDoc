import os, time, sqlite3
from datetime import timedelta
from flask import (
    Flask, render_template, request, send_file,
    redirect, url_for, session, flash, abort
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Optional: Razorpay (only if you will accept payments)
try:
    import razorpay
except Exception:
    razorpay = None

# -------------------------
# App & Config
# -------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change_this_to_a_long_random_secret")

# Keep user logged-in until they logout
app.permanent_session_lifetime = timedelta(days=365)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static"), exist_ok=True)

# -------------------------
# Database (SQLite)
# -------------------------
DB_PATH = os.path.join(BASE_DIR, "users.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
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
            subscription_expiry INTEGER,   -- epoch seconds; if > now = active
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

# -------------------------
# Optional: Razorpay init
# -------------------------
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)) if (razorpay and RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET) else None

# -------------------------
# Utilities
# -------------------------
def clean_old_uploads(folder, max_age_minutes=60):
    now = time.time()
    max_age = max_age_minutes * 60
    for filename in os.listdir(folder):
        path = os.path.join(folder, filename)
        if os.path.isfile(path):
            try:
                if now - os.path.getmtime(path) > max_age:
                    os.remove(path)
            except Exception:
                pass

def save_uploaded_file(file_storage):
    filename = secure_filename(file_storage.filename)
    # ensure unique filename
    base, ext = os.path.splitext(filename)
    i = 1
    out_name = filename
    while os.path.exists(os.path.join(UPLOAD_FOLDER, out_name)):
        i += 1
        out_name = f"{base}_{i}{ext}"
    path = os.path.join(UPLOAD_FOLDER, out_name)
    file_storage.save(path)
    return out_name, path

def is_subscribed(user_row):
    if not user_row: return False
    exp = user_row.get("subscription_expiry")
    if not exp: return False
    try:
        return int(exp) > int(time.time())
    except Exception:
        return False

from functools import wraps
def login_required(f):
    @wraps(f)
    def _wrap(*a, **k):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return f(*a, **k)
    return _wrap

@app.before_request
def keep_session_permanent():
    # Only mark permanent if logged-in; avoids setting cookie for every visitor
    if "user_id" in session:
        session.permanent = True

# -------------------------
# AUTH: Signup / Login / Logout
# -------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        name = request.form.get("name","").strip() or None

        if not email or not password:
            flash("Email and Password are required.", "danger")
            return render_template("signup.html")

        try:
            hashed = generate_password_hash(password)
            conn = get_db_connection()
            conn.execute("INSERT INTO users (email, password, name) VALUES (?, ?, ?)", (email, hashed, name))
            conn.commit()
            conn.close()
            flash("Signup successful! Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")
        except Exception as e:
            flash(f"Error: {e}", "danger")

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["email"]   = user["email"]
            session["user_name"] = user["name"]
            flash("Logged in successfully!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# INDEX: Dashboard/Home
# -------------------------
@app.route("/")
def index():
    user = None
    tasks_done = 0
    subscribed = False
    if "user_id" in session:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT email, tasks_done, subscription_expiry FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()
        conn.close()
        if row:
            user = row["email"]
            tasks_done = row["tasks_done"] or 0
            subscribed = is_subscribed(row)

    return render_template("index.html",
                           user=user,
                           tasks_done=tasks_done,
                           is_subscribed=subscribed,
                           razorpay_enabled=bool(razorpay_client))

# -------------------------
# Highlight Route (example)
# -------------------------
# NOTE: You must have a function `process_files(pdf_path, excel_path, mode, output_dir)`
# in a local module highlight.py. If not available, replace with your own logic.
try:
    from highlight import process_files  # user-provided module
except Exception:
    process_files = None

@app.route("/highlight", methods=["POST"])
@login_required
def highlight_route():
    if not process_files:
        flash("Highlight feature is not configured on this server.", "danger")
        return redirect(url_for("index"))

    clean_old_uploads(UPLOAD_FOLDER)

    # Free users: 2 tasks limit
    conn = get_db_connection()
    row = conn.execute("SELECT tasks_done, subscription_expiry FROM users WHERE id=?",(session["user_id"],)).fetchone()
    conn.close()

    subscribed = is_subscribed(row)
    tasks_done = (row["tasks_done"] or 0) if row else 0

    if (not subscribed) and tasks_done >= 2:
        return render_template("limit.html"), 403

    pdf_file = request.files.get("pdf_file")
    excel_file = request.files.get("excel_file")
    highlight_type = request.form.get("highlight_type")

    if not pdf_file or not excel_file or highlight_type not in {"uan","esic"}:
        flash("Please upload PDF & Excel and select type (UAN/ESIC).", "danger")
        return redirect(url_for("index"))

    pdf_name, pdf_path = save_uploaded_file(pdf_file)
    excel_name, excel_path = save_uploaded_file(excel_file)

    out_pdf, not_found_excel = process_files(
        pdf_path=pdf_path,
        excel_path=excel_path,
        mode=highlight_type,
        output_dir=UPLOAD_FOLDER
    )

    # increment tasks
    conn = get_db_connection()
    conn.execute("UPDATE users SET tasks_done = COALESCE(tasks_done,0) + 1 WHERE id=?", (session["user_id"],))
    conn.commit()
    conn.close()

    # Expect out_pdf & not_found_excel are absolute paths → send names to template
    return render_template("result.html",
                           out_pdf=os.path.basename(out_pdf) if out_pdf else None,
                           not_found_excel=os.path.basename(not_found_excel) if not_found_excel else None)

# -------------------------
# Safe Download Routes
# -------------------------
@app.route("/download_pdf")
@login_required
def download_pdf():
    filename = request.args.get("file")
    if not filename:
        abort(404)
    path = os.path.join(UPLOAD_FOLDER, os.path.basename(filename))
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)

@app.route("/download_excel")
@login_required
def download_excel():
    filename = request.args.get("file")
    if not filename:
        abort(404)
    path = os.path.join(UPLOAD_FOLDER, os.path.basename(filename))
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)

# -------------------------
# Plans & Payment (Razorpay)
# -------------------------
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

    return render_template("payment.html",
                           razorpay_merchant_key=RAZORPAY_KEY_ID,
                           razorpay_order_id=order["id"],
                           amount=amount_paise,
                           currency="INR",
                           user_email=session.get("email",""))

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
            "razorpay_signature": signature
        })
        # success → add 30 days
        expiry = int(time.time()) + 30*24*3600
        conn = get_db_connection()
        conn.execute("UPDATE users SET subscription_expiry=? WHERE id=?", (expiry, session["user_id"]))
        conn.commit()
        conn.close()
        flash("Payment successful! Subscription activated for 30 days.", "success")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Payment verification failed: {e}", "danger")
        return redirect(url_for("plans"))

# -------------------------
# Informational Pages
# -------------------------
@app.route("/about")
def about(): return render_template("page.html", title="About", content="About We ❤️ Doc")

@app.route("/contact")
def contact(): return render_template("page.html", title="Contact", content="Contact us at support@welovedoc.in")

@app.route("/privacy")
def privacy(): return render_template("page.html", title="Privacy Policy", content="Your privacy is important to us.")

@app.route("/refunds")
def refunds(): return render_template("page.html", title="Refund Policy", content="Refund policy details here.")

@app.route("/shipping")
def shipping(): return render_template("page.html", title="Shipping Policy", content="Digital product. No shipping.")

@app.route("/terms")
def terms(): return render_template("page.html", title="Terms", content="Terms of service details here.")

@app.route('/sitemap.xml')
def sitemap():
    lastmod = time.strftime("%Y-%m-%d")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://welovedoc.in/</loc><lastmod>{lastmod}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>
</urlset>"""
    return xml, 200, {'Content-Type': 'application/xml'}

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
