import os
import uuid
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
from highlight_feature import process_files

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html", user=None, is_subscribed=False, sub_expiry_date=None)

@app.route("/highlight", methods=["POST"])
def highlight_route():
    pdf_file = request.files.get("pdf_file")
    excel_file = request.files.get("excel_file")
    highlight_type = request.form.get("highlight_type", "uan")

    if not pdf_file or not excel_file:
        flash("Please upload both PDF and Excel files.")
        return redirect(url_for("index"))

    pdf_filename = secure_filename(pdf_file.filename)
    excel_filename = secure_filename(excel_file.filename)

    pdf_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{pdf_filename}")
    excel_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{excel_filename}")
    pdf_file.save(pdf_path)
    excel_file.save(excel_path)

    task_output = os.path.join(OUTPUT_FOLDER, str(uuid.uuid4()))
    os.makedirs(task_output, exist_ok=True)

    result = process_files(pdf_path, excel_path, task_output, highlight_type=highlight_type)

    if isinstance(result, tuple):
        out_pdf = result[0]
    else:
        out_pdf = result

    if not os.path.exists(out_pdf):
        return "Processing failed: output file not found.", 500

    return send_file(out_pdf, as_attachment=True)

# Placeholder routes
@app.route("/plans")     def plans(): return "<h2>Subscription plans (placeholder)</h2>"
@app.route("/login")     def login(): return "<h2>Login (placeholder)</h2>"
@app.route("/signup")    def signup(): return "<h2>Sign up (placeholder)</h2>"
@app.route("/logout")    def logout(): return redirect(url_for("index"))
@app.route("/about")     def about(): return "<h2>About (placeholder)</h2>"
@app.route("/refund")    def refund(): return "<h2>Refund policy (placeholder)</h2>"
@app.route("/shipping")  def shipping(): return "<h2>Shipping (placeholder)</h2>"
@app.route("/terms")     def terms(): return "<h2>Terms (placeholder)</h2>"
@app.route("/privacy")   def privacy(): return "<h2>Privacy (placeholder)</h2>"
@app.route("/contact")   def contact(): return "<h2>Contact (placeholder)</h2>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
