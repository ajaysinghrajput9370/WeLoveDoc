from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import os
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from highlight import process_files
import razorpay

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Configuration
UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Razorpay Setup
app.config['RAZORPAY_KEY_ID'] = 'your_razorpay_key_id'
app.config['RAZORPAY_KEY_SECRET'] = 'your_razorpay_key_secret'
razorpay_client = razorpay.Client(auth=(app.config['RAZORPAY_KEY_ID'], app.config['RAZORPAY_KEY_SECRET']))

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
                subscription_expiry TEXT,
                tasks_remaining INTEGER DEFAULT 2
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                payment_id TEXT,
                amount INTEGER,
                date TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
    print("Database ready!")

init_db()

# ------------------ Helper Functions ------------------
def check_subscription(username):
    with get_db_connection() as conn:
        user = conn.execute("SELECT subscription_expiry FROM users WHERE username=?", (username,)).fetchone()
        if user and user["subscription_expiry"]:
            expiry_date = datetime.strptime(user["subscription_expiry"], "%Y-%m-%d")
            return expiry_date > datetime.now()
    return False

def update_task_count(username):
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET tasks_remaining = tasks_remaining - 1 WHERE username=?", (username,))
        conn.commit()

def get_task_count(username):
    with get_db_connection() as conn:
        user = conn.execute("SELECT tasks_remaining FROM users WHERE username=?", (username,)).fetchone()
        return user["tasks_remaining"] if user else 0

# ------------------ Routes ------------------
@app.route("/")
def index():
    username = session.get("username")
    is_subscribed = False
    sub_expiry_date = None
    tasks_remaining = 0

    if username:
        with get_db_connection() as conn:
            user = conn.execute("SELECT subscription_expiry, tasks_remaining FROM users WHERE username=?", (username,)).fetchone()
            if user:
                sub_expiry_date = user["subscription_expiry"]
                is_subscribed = sub_expiry_date and datetime.strptime(sub_expiry_date, "%Y-%m-%d") > datetime.now()
                tasks_remaining = user["tasks_remaining"]

    return render_template("index.html", 
                         user=username, 
                         is_subscribed=is_subscribed, 
                         sub_expiry_date=sub_expiry_date,
                         tasks_remaining=tasks_remaining)

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
            user = conn.execute("SELECT id, username, password FROM users WHERE username=?", (username,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["username"] = user["username"]
            session["user_id"] = user["id"]
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("user_id", None)
    flash("Logged out successfully", "info")
    return redirect(url_for("index"))

# ------------------ Highlight Route ------------------
@app.route("/highlight", methods=["POST"])
def highlight_route():
    if "username" not in session:
        flash("Please log in to use this feature", "warning")
        return redirect(url_for("login"))

    username = session["username"]
    is_subscribed = check_subscription(username)
    tasks_remaining = get_task_count(username)

    if not is_subscribed and tasks_remaining <= 0:
        flash("Free task limit reached. Please subscribe for unlimited access.", "warning")
        return redirect(url_for("plans"))

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
        result_pdf, result_excel = process_files(pdf_path, excel_path, highlight_type, RESULT_FOLDER)
        
        if not is_subscribed:
            update_task_count(username)
            
        return render_template("download.html", 
                             pdf_file=os.path.basename(result_pdf),
                             excel_file=os.path.basename(result_excel) if result_excel else None)
    except Exception as e:
        flash(f"Error processing files: {str(e)}", "danger")
        return redirect(url_for("index"))

@app.route("/download/<filename>")
def download_file(filename):
    path = os.path.join(RESULT_FOLDER, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    flash("File not found", "danger")
    return redirect(url_for("index"))

# ------------------ Subscription Routes ------------------
@app.route("/plans")
def plans():
    return render_template("plans.html", 
                         razorpay_enabled=bool(app.config['RAZORPAY_KEY_ID']),
                         user=session.get("username"))

@app.route("/create_order", methods=["POST"])
def create_order():
    if "username" not in session:
        return redirect(url_for("login"))
    
    amount = int(request.form["amount"]) * 100  # Convert to paise
    order_data = {
        'amount': amount,
        'currency': 'INR',
        'receipt': f'sub_{session["username"]}',
        'payment_capture': '1'
    }
    
    try:
        order = razorpay_client.order.create(data=order_data)
        return render_template("payment.html",
                             amount=amount,
                             razorpay_order_id=order["id"],
                             razorpay_merchant_key=app.config['RAZORPAY_KEY_ID'],
                             user_email=session.get("username"))
    except Exception as e:
        flash(f"Payment error: {str(e)}", "danger")
        return redirect(url_for("plans"))

@app.route("/payment_success", methods=["POST"])
def payment_success():
    if "username" not in session:
        return redirect(url_for("login"))
    
    payment_id = request.form["razorpay_payment_id"]
    order_id = request.form["razorpay_order_id"]
    signature = request.form["razorpay_signature"]
    
    try:
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        
        # Verify payment signature
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Update user subscription
        expiry_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        with get_db_connection() as conn:
            conn.execute("UPDATE users SET subscription_expiry=?, tasks_remaining=999 WHERE username=?", 
                        (expiry_date, session["username"]))
            conn.execute("INSERT INTO payments (user_id, payment_id, amount, date) VALUES (?, ?, ?, ?)",
                        (session["user_id"], payment_id, params_dict.get('amount', 0), datetime.now().strftime("%Y-%m-%d")))
        
        flash("Payment successful! Your subscription is now active.", "success")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Payment verification failed: {str(e)}", "danger")
        return redirect(url_for("plans"))

# ------------------ Static Pages ------------------
@app.route("/about")
def about(): return render_template("page.html", title="About Us", content="Information about our service.")

@app.route("/privacy")
def privacy(): return render_template("page.html", title="Privacy Policy", content="Our privacy policy details.")

@app.route("/terms")
def terms(): return render_template("page.html", title="Terms of Service", content="Our terms and conditions.")

@app.route("/refund")
def refund(): return render_template("page.html", title="Refund Policy", content="Our refund policy details.")

@app.route("/shipping")
def shipping(): return render_template("page.html", title="Shipping", content="Shipping information.")

@app.route("/contact")
def contact(): return render_template("page.html", title="Contact Us", content="How to reach us.")

if __name__ == "__main__":
    app.run(debug=True)
