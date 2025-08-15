from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import os
import uuid
from werkzeug.utils import secure_filename
from highlight_feature import process_files
from database import get_db_connection, init_db
import datetime
import razorpay

app = Flask(__name__)
app.secret_key = "sOUMU"  # Change for production

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

# ---------------- Routes ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        pdf_file = request.files.get("pdf_file")
        excel_file = request.files.get("excel_file")
        if not pdf_file or not excel_file:
            flash("Select both PDF and Excel files!")
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

# Download routes
@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(RESULT_FOLDER, filename)
    return send_file(file_path, as_attachment=True)

# Login/Signup routes
@app.route("/login", methods=["GET", "POST"])
def login():
    # Implement login using DB
    pass

@app.route("/signup", methods=["GET", "POST"])
def signup():
    # Implement signup using DB
    pass

@app.route("/dashboard")
def dashboard():
    # Show user dashboard with subscription info
    pass

if __name__ == "__main__":
    app.run(debug=True)
