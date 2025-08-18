from flask import Flask, render_template, request, send_file, redirect, url_for, flash, session, jsonify
import os
import warnings
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import uuid
from datetime import datetime, timedelta
from functools import wraps
from highlight_feature import highlight_pdf
import razorpay
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

warnings.filterwarnings("ignore", category=UserWarning, module="razorpay")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ---------------------- DB Helper ----------------------
def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        with open("schema.sql") as f:
            conn.executescript(f.read())

def clear_uploads():
    for folder in [UPLOAD_FOLDER, RESULTS_FOLDER]:
        for f in os.listdir(folder):
            os.remove(os.path.join(folder, f))

def user_can_highlight():
    user_id = session.get("user_id")
    device_id = session.get("device_id")
    if not user_id or not device_id:
        return False

    conn = get_db_connection()
    user = conn.execute(
        "SELECT subscription_active, device_id, subscription_end FROM users WHERE id=?", (user_id,)
    ).fetchone()
    conn.close()

    if not user or user["device_id"] != device_id or user["subscription_active"] != 1:
        return False

    if user["subscription_end"]:
        expiry = datetime.fromisoformat(user["subscription_end"])
        if datetime.now() > expiry:
            conn = get_db_connection()
            conn.execute("UPDATE users SET subscription_active=0 WHERE id=?", (user_id,))
            conn.commit()
            conn.close()
            return False
    return True

# ---------------------- Decorators ----------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def subscription_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first", "danger")
            return redirect(url_for("login"))
        if not user_can_highlight():
            flash("You need an active subscription to access this feature.", "warning")
            return redirect(url_for("subscribe"))
        return f(*args, **kwargs)
    return decorated_function

# ---------------------- Routes ----------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        device_id = str(uuid.uuid4())

        conn = get_db_connection()
        try:
            password_hash = generate_password_hash(password)
            conn.execute(
                "INSERT INTO users (email, password_hash, device_id, subscription_active) VALUES (?, ?, ?, 0)",
                (email, password_hash, device_id)
            )
            conn.commit()
            user_id = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
            session["user_id"] = user_id
            session["device_id"] = device_id
            flash("Signup successful! Please subscribe to use highlight feature.")
            return redirect(url_for("subscribe"))
        except sqlite3.IntegrityError:
            flash("Email already registered.")
        finally:
            conn.close()
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["device_id"] = user["device_id"]
            flash("Login successful!")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for("login"))

@app.route("/subscribe", methods=["GET", "POST"])
def subscribe():
    if "user_id" not in session:
        flash("Login first to subscribe.")
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "Payment data missing. Please try again."})

            payment_id = data.get("razorpay_payment_id")
            signature = data.get("razorpay_signature")
            order_id = data.get("razorpay_order_id")
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"success": False, "message": "Session expired. Please login again."})

            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })

            start_date = datetime.now()
            end_date = start_date + timedelta(days=30)

            conn = get_db_connection()
            conn.execute(
                "UPDATE users SET subscription_active=1, subscription_start=?, subscription_end=? WHERE id=?",
                (start_date.isoformat(), end_date.isoformat(), user_id)
            )
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "Subscription activated!"})
        except Exception as e:
            return jsonify({"success": False, "message": f"Payment verification failed: {str(e)}"})

    return render_template("subscribe.html", razorpay_key_id=RAZORPAY_KEY_ID)

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/highlight", methods=["GET", "POST"])
@subscription_required
def highlight():
    return render_template("highlight.html")

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    output_pdf = None
    not_found_excel = None

    conn = get_db_connection()
    user = conn.execute("SELECT email FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    username = user["email"] if user else "User"

    can_highlight = user_can_highlight()  # <-- template me variable pass

    if request.method == "POST":
        if request.form.get("action") == "refresh":
            clear_uploads()
            flash("Uploads and results cleared. Ready for new task.")
            return redirect(url_for("index"))

        if not can_highlight:
            flash("Highlight feature requires a paid subscription.")
            return redirect(url_for("subscribe"))

        clear_uploads()
        pdf_file = request.files.get("pdf")
        excel_file = request.files.get("excel")
        highlight_type = request.form.get("highlight_type")

        if not pdf_file or not excel_file:
            flash("Both PDF and Excel are required.")
            return redirect(request.url)

        pdf_path = os.path.join(UPLOAD_FOLDER, secure_filename(pdf_file.filename))
        excel_path = os.path.join(UPLOAD_FOLDER, secure_filename(excel_file.filename))
        pdf_file.save(pdf_path)
        excel_file.save(excel_path)

        output_pdf, not_found_excel = highlight_pdf(pdf_path, excel_path, highlight_type, RESULTS_FOLDER)

    return render_template(
        "index.html",
        output_pdf=output_pdf,
        not_found_excel=not_found_excel,
        username=username,
        can_highlight=can_highlight
    )

@app.route("/download/<filename>")
def download_file(filename):
    return send_file(os.path.join(RESULTS_FOLDER, filename), as_attachment=True)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
