from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash
import os, time, sqlite3, datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from highlight import process_files
from database import get_db_connection, init_db
import razorpay

# -------------------------
# App Setup
# -------------------------
app = Flask(__name__)
app.secret_key = "sOUMU"  # Security key
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("static", exist_ok=True)

# Razorpay client
razorpay_client = razorpay.Client(
    auth=(os.environ.get("RAZORPAY_KEY_ID"), os.environ.get("RAZORPAY_KEY_SECRET"))
)

# -------------------------
# Helper Functions
# -------------------------
def clean_old_uploads(folder, max_age_minutes=30):
    now = time.time()
    max_age = max_age_minutes * 60
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path) and now - os.path.getmtime(file_path) > max_age:
            try: os.remove(file_path)
            except Exception: pass

def save_uploaded_file(file_storage):
    filename = secure_filename(file_storage.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file_storage.save(file_path)
    return file_path

# -------------------------
# Auth Routes
# -------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email/Password required", "danger")
            return render_template("signup.html")
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)",
                      (email, generate_password_hash(password)))
            conn.commit()
            flash("Signup successful! Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered!", "danger")
        finally:
            conn.close()
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, password FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["email"] = email
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials!", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))

# -------------------------
# Razorpay Routes
# -------------------------
@app.route("/create_order", methods=["POST"])
def create_order():
    amount = int(request.form.get("amount")) * 100  # ₹ → paise
    currency = "INR"
    receipt = f"order_rcptid_{int(time.time())}"
    razorpay_order = razorpay_client.order.create(dict(
        amount=amount,
        currency=currency,
        receipt=receipt,
        payment_capture='1'
    ))
    return render_template("payment.html",
                           razorpay_order_id=razorpay_order['id'],
                           razorpay_merchant_key=os.environ.get("RAZORPAY_KEY_ID"),
                           amount=amount,
                           currency=currency,
                           user_email=session.get("email", ""))

@app.route("/payment_success", methods=["POST"])
def payment_success():
    payment_id = request.form.get("razorpay_payment_id")
    order_id = request.form.get("razorpay_order_id")
    signature = request.form.get("razorpay_signature")
    try:
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        razorpay_client.utility.verify_payment_signature(params_dict)
        now = int(time.time())
        expiry = now + 30*24*3600  # 30 days subscription
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE users SET subscription_expiry=? WHERE email=?", (expiry, session.get("email")))
        conn.commit()
        conn.close()
        flash("Payment successful! Subscription activated.", "success")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Payment verification failed: {str(e)}", "danger")
        return redirect(url_for("plans"))

@app.route("/subscribe_dummy")
def subscribe_dummy():
    if "user_id" not in session: return redirect(url_for("login"))
    now = int(time.time())
    expiry = now + 30*24*3600
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET subscription_expiry=?, tasks_done=0 WHERE id=?", (expiry, session["user_id"]))
    conn.commit()
    conn.close()
    flash("Subscription activated for 30 days (demo).", "success")
    return redirect(url_for("index"))

# -------------------------
# Main Pages / Highlight
# -------------------------
@app.route("/")
def index():
    user, is_subscribed, tasks_done = None, False, 0
    if "user_id" in session:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT email, tasks_done, subscription_expiry FROM users WHERE id=?", (session["user_id"],))
        row = c.fetchone()
        conn.close()
        if row:
            user = row[0]
            tasks_done = row[1] or 0
            sub_expiry = row[2]
            is_subscribed = bool(sub_expiry and sub_expiry > int(time.time()))
    return render_template("index.html",
                           user=user,
                           is_subscribed=is_subscribed,
                           tasks_done=tasks_done)

@app.route("/highlight", methods=["POST"])
def highlight_route():
    clean_old_uploads(UPLOAD_FOLDER)
    if "user_id" not in session:
        return "<h3>Please login</h3><a href='/login'>Login</a>", 403
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT tasks_done, subscription_expiry FROM users WHERE id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()
    now = int(time.time())
    tasks_done = row[0] if row else 0
    sub_expiry = row[1] if row else None
    is_subscribed = bool(sub_expiry and sub_expiry > now)
    if not is_subscribed and tasks_done >= 2:
        return render_template("subscription_limit.html"), 403

    pdf_file = request.files.get("pdf_file")
    excel_file = request.files.get("excel_file")
    highlight_type = request.form.get("highlight_type")
    if not pdf_file or not excel_file or highlight_type not in {"uan", "esic"}:
        flash("Please upload both PDF and Excel, and select UAN or ESIC.", "danger")
        return redirect(url_for("index"))

    pdf_path = save_uploaded_file(pdf_file)
    excel_path = save_uploaded_file(excel_file)

    out_pdf, not_found_excel = process_files(pdf_path, excel_path, highlight_type, UPLOAD_FOLDER)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET tasks_done = COALESCE(tasks_done, 0) + 1 WHERE id=?", (session["user_id"],))
    conn.commit()
    conn.close()

    return render_template("result.html", out_pdf=out_pdf, not_found_excel=not_found_excel)

# -------------------------
# Download routes
# -------------------------
@app.route("/download_pdf")
def download_pdf():
    path = request.args.get("path", "")
    if not os.path.exists(path): return "File not found", 404
    return send_file(path, as_attachment=True)

@app.route("/download_excel")
def download_excel():
    path = request.args.get("path", "")
    if not os.path.exists(path): return "Data_Not_Found.xlsx not available.", 404
    return send_file(path, as_attachment=True)

# -------------------------
# Static Pages
# -------------------------
for page in ["about", "contact", "privacy", "refunds", "shipping", "terms"]:
    app.add_url_rule(f"/{page}", page, lambda p=page: render_template(f"{p}.html"))

# -------------------------
# Init DB
# -------------------------
with app.app_context(): init_db()

if __name__ == "__main__":
    app.run(debug=True)
