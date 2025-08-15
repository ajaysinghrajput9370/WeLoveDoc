from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import os, uuid, datetime
from werkzeug.utils import secure_filename
from database import init_db, add_user, validate_user, get_user_by_id
from highlight_feature import process_files
import razorpay

app = Flask(__name__)
app.secret_key = "sOUMU"  # Change in production

UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Razorpay config
RAZORPAY_KEY = "YOUR_KEY_HERE"
RAZORPAY_SECRET = "YOUR_SECRET_HERE"
client = razorpay.Client(auth=(RAZORPAY_KEY, RAZORPAY_SECRET))

# Initialize DB
init_db()

# ---------------- ROUTES ---------------- #

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        pdf_file = request.files.get("pdf_file")
        excel_file = request.files.get("excel_file")
        if not pdf_file or not excel_file:
            flash("Please select both PDF and Excel files!")
            return redirect(request.url)

        pdf_filename = secure_filename(pdf_file.filename)
        excel_filename = secure_filename(excel_file.filename)
        pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
        excel_path = os.path.join(UPLOAD_FOLDER, excel_filename)
        pdf_file.save(pdf_path)
        excel_file.save(excel_path)

        output_pdf, not_found_excel = process_files(pdf_path, excel_path, RESULT_FOLDER)
        return render_template("results.html", pdf_file=output_pdf, excel_file=not_found_excel)

    return render_template("index.html")

# Download processed files
@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(RESULT_FOLDER, filename)
    return send_file(file_path, as_attachment=True)

# ---------------- Auth ---------------- #

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        add_user(name,email,password)
        flash("Signup successful. Please login.")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = validate_user(email,password)
        if user:
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials!")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out successfully.")
    return redirect(url_for("index"))

# ---------------- Dashboard ---------------- #

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    return render_template("dashboard.html", user=user)

# ---------------- Static Pages ---------------- #

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/plans")
def plans():
    # Example plan details
    plans = [
        {"duration":1, "devices":1, "price":299},
        {"duration":1, "devices":2, "price":499},
        {"duration":6, "devices":1, "price":799},
        {"duration":6, "devices":2, "price":1199},
        {"duration":12,"devices":1,"price":1499},
        {"duration":12,"devices":2,"price":2499},
    ]
    return render_template("plans.html", plans=plans, razorpay_key=RAZORPAY_KEY)

# ---------------- Razorpay Payment Callback ---------------- #

@app.route("/payment_success", methods=["POST"])
def payment_success():
    # Capture payment here, update DB accordingly
    # For now just flash message
    flash("Payment successful! Subscription updated.")
    return redirect(url_for("dashboard"))

# ---------------- Run App ---------------- #

if __name__ == "__main__":
    app.run(debug=True)
