from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash
import os
import time
import sqlite3
import razorpay

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from highlight import process_files
from database import get_db_connection, init_db

app = Flask(__name__)
app.secret_key = "sOUMU"   # सुरक्षा के लिए इसे बदलें

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("static", exist_ok=True)

# -------------------------
# Auto delete old files (30 minutes)
# -------------------------
def clean_old_uploads(folder, max_age_minutes=30):
    now = time.time()
    max_age = max_age_minutes * 60
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            if now - os.path.getmtime(file_path) > max_age:
                try:
                    os.remove(file_path)
                except Exception:
                    pass

# -------------------------
# Save uploaded file helper
# -------------------------
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
            c.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, generate_password_hash(password))
            )
            conn.commit()
            flash("Signup successful! Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered!", "danger")
        finally:
            conn.close()
    return render_template("signup.html")

import datetime

@app.route('/sitemap.xml')
def sitemap():
    lastmod = datetime.date.today().isoformat()
    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://welovedoc.in/</loc>
        <lastmod>{lastmod}</lastmod>
        <priority>1.00</priority>
    </url>
</urlset>
"""
    return sitemap_xml, 200, {'Content-Type': 'application/xml'}
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
# Optional: Dummy subscription (30 days)
# NOTE: production में payment gateway के बाद ही enable करें
# -------------------------
@app.route("/subscribe_dummy")
def subscribe_dummy():
    if "user_id" not in session:
        return redirect(url_for("login"))
    now = int(time.time())
    expiry = now + 30 * 24 * 3600  # 30 days
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET subscription_expiry=?, tasks_done=0 WHERE id=?",
              (expiry, session["user_id"]))
    conn.commit()
    conn.close()
    flash("Subscription activated for 30 days (demo).", "success")
    return redirect(url_for("index"))
@app.route("/create_order", methods=["POST"])
def create_order():
    amount = int(request.form.get("amount")) * 100  # ₹ → paise
    currency = "INR"
    receipt = f"order_rcptid_{int(time.time())}"

    # Razorpay order create
    razorpay_order = razorpay_client.order.create(dict(
        amount=amount,
        currency=currency,
        receipt=receipt,
        payment_capture='1'
    ))

    return render_template("payment.html",
                           razorpay_order_id=razorpay_order['id'],
                           razorpay_merchant_key=RAZORPAY_KEY_ID,
                           amount=amount,
                           currency=currency,
                           user_email=session.get("email", ""))
@app.route("/payment_success", methods=["POST"])
def payment_success():
    payment_id = request.form.get("razorpay_payment_id")
    order_id = request.form.get("razorpay_order_id")
    signature = request.form.get("razorpay_signature")

    # Optional: verify payment signature
    try:
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        razorpay_client.utility.verify_payment_signature(params_dict)

        # Payment successful → update user subscription
        now = int(time.time())
        expiry = now + 30*24*3600  # 30 days subscription example
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

# -------------------------
# Plans page (show plan chart here)
# -------------------------
@app.route("/plans")
def plans():
    # Tumhara plan chart yahan template me show hoga.
    # Agar tumne plan data bheja hai to yeh template me dynamically dikhaya ja sakta hai.
    return render_template("plans.html")


# -------------------------
# Pages
# -------------------------
@app.route("/")
def index():
    # show user status to template (login/subscribed/tasks)
    user = None
    is_subscribed = False
    tasks_done = 0
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
            now = int(time.time())
            is_subscribed = bool(sub_expiry and sub_expiry > now)

    return render_template("index.html",
                           user=user,
                           is_subscribed=is_subscribed,
                           tasks_done=tasks_done)

@app.route("/highlight", methods=["POST"])
def highlight_route():
    clean_old_uploads(UPLOAD_FOLDER)  # 30 मिनट से पुराने files हटाएँ

    # Must be logged-in
    if "user_id" not in session:
        return """
        <h3 style='font-family:Arial;color:#d32f2f'>Please login to use this feature.</h3>
        <a href='/login'>Login</a> | <a href='/signup'>Signup</a>
        """, 403

    # Task limit check
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT tasks_done, subscription_expiry FROM users WHERE id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()

    now = int(time.time())
    tasks_done = row[0] if row else 0
    sub_expiry = row[1] if row else None
    is_subscribed = bool(sub_expiry and sub_expiry > now)

    # Free users: only 2 tasks
    if not is_subscribed and tasks_done >= 2:
        return """
        <html><body style="font-family:Arial;text-align:center;padding:40px;background:#f9f9f9">
          <div style="display:inline-block;background:#fff;padding:30px;border-radius:12px;box-shadow:0 0 15px rgba(0,0,0,0.1)">
            <h3 style="color:#d32f2f">Free task limit reached (2/2)</h3>
            <p>Please subscribe to continue.</p>
            <a href="/plans" style="background:#1976d2;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none">View Plans</a>
          </div>
        </body></html>
        """, 403

    # Inputs
    pdf_file = request.files.get("pdf_file")
    excel_file = request.files.get("excel_file")
    highlight_type = request.form.get("highlight_type")

    if not pdf_file or not excel_file or highlight_type not in {"uan", "esic"}:
        flash("Please upload both PDF and Excel, and select UAN or ESIC.", "danger")
        return redirect(url_for("index"))

    pdf_path = save_uploaded_file(pdf_file)
    excel_path = save_uploaded_file(excel_file)

    out_pdf, not_found_excel = process_files(
        pdf_path=pdf_path,
        excel_path=excel_path,
        mode=highlight_type,
        output_dir=UPLOAD_FOLDER
    )

    # Success → increment task count (free or paid both)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET tasks_done = COALESCE(tasks_done, 0) + 1 WHERE id=?", (session["user_id"],))
    conn.commit()
    conn.close()

    # Redirect to result download page (or show inline)
    return render_template("result.html", out_pdf=out_pdf, not_found_excel=not_found_excel)

@app.route("/download_pdf")
def download_pdf():
    path = request.args.get("path", "")
    if not os.path.exists(path):
        return "File not found", 404
    return send_file(path, as_attachment=True)

@app.route("/download_excel")
def download_excel():
    path = request.args.get("path", "")
    if not os.path.exists(path):
        return "Data_Not_Found.xlsx not available.", 404
    return send_file(path, as_attachment=True)

# Static Pages
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
# -------------------------
# Init DB on start
# -------------------------
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
