from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import razorpay
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Change this in production

# Razorpay keys (replace with your own)
RAZORPAY_KEY_ID = "rzp_test_xxxxxxx"
RAZORPAY_KEY_SECRET = "xxxxxxxx"
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

DB_FILE = "database.db"


# -------------------- DATABASE INIT --------------------
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Users table
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            subscription TEXT DEFAULT 'free'
        )
        """)
        # Payments table
        c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan TEXT,
            amount INTEGER,
            payment_id TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()


# -------------------- DB CONNECTION --------------------
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------- HOME --------------------
@app.route("/")
def home():
    return render_template("home.html")


# -------------------- SIGNUP --------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not email or not password:
            flash("Email and password are required", "error")
            return redirect(url_for("signup"))

        hashed_pw = generate_password_hash(password)

        try:
            conn = get_db_connection()
            conn.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_pw))
            conn.commit()
            conn.close()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists", "error")
            return redirect(url_for("signup"))

    return render_template("signup.html")


# -------------------- LOGIN --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["subscription"] = user["subscription"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password", "error")

    return render_template("login.html")


# -------------------- LOGOUT --------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("home"))


# -------------------- DASHBOARD --------------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=session)


# -------------------- SUBSCRIPTION PLANS --------------------
@app.route("/plans")
def plans():
    return render_template("plans.html")


# -------------------- CREATE PAYMENT --------------------
@app.route("/create_order/<plan>")
def create_order(plan):
    if "user_id" not in session:
        return redirect(url_for("login"))

    plans_price = {
        "monthly": 29900,  # in paise (₹299)
        "quarterly": 79900,  # ₹799
        "yearly": 299900  # ₹2999
    }

    if plan not in plans_price:
        flash("Invalid plan", "error")
        return redirect(url_for("plans"))

    amount = plans_price[plan]
    order = razorpay_client.order.create({"amount": amount, "currency": "INR", "payment_capture": "1"})

    conn = get_db_connection()
    conn.execute("INSERT INTO payments (user_id, plan, amount, payment_id, status) VALUES (?, ?, ?, ?, ?)",
                 (session["user_id"], plan, amount, order["id"], "created"))
    conn.commit()
    conn.close()

    return render_template("payment.html", order=order, plan=plan, amount=amount / 100, key_id=RAZORPAY_KEY_ID)


# -------------------- PAYMENT SUCCESS --------------------
@app.route("/payment_success", methods=["POST"])
def payment_success():
    payment_id = request.form.get("razorpay_payment_id")
    order_id = request.form.get("razorpay_order_id")
    signature = request.form.get("razorpay_signature")

    # Here, ideally verify payment signature from Razorpay

    conn = get_db_connection()
    conn.execute("UPDATE payments SET status = ? WHERE payment_id = ?", ("paid", order_id))
    conn.execute("UPDATE users SET subscription = ? WHERE id = ?", ("paid", session["user_id"]))
    conn.commit()
    conn.close()

    session["subscription"] = "paid"
    flash("Payment successful! Subscription activated.", "success")
    return redirect(url_for("dashboard"))


# -------------------- SIMPLE PAGES --------------------
@app.route("/about")
def about():
    return render_template("page.html", title="About", content="About We ❤️ Doc")


@app.route("/contact")
def contact():
    return render_template("page.html", title="Contact", content="Contact us at support@welovedoc.in")


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
