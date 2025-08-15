from flask import Flask, render_template, request, send_file
import os
from highlight_feature import process_files  # Make sure this file exists

app = Flask(__name__)

# Home page
@app.route("/")
def index():
    return render_template("index.html", is_subscribed=False)

# Highlight route
@app.route("/highlight", methods=["POST"])
def highlight_route():
    pdf_file = request.files["pdf_file"]
    excel_file = request.files["excel_file"]
    highlight_type = request.form.get("highlight_type", "uan")

    # Save uploaded files
    pdf_path = os.path.join("uploads", pdf_file.filename)
    excel_path = os.path.join("uploads", excel_file.filename)
    os.makedirs("uploads", exist_ok=True)
    pdf_file.save(pdf_path)
    excel_file.save(excel_path)

    # Process
    output_path = process_files(pdf_path, excel_path, highlight_type)

    return send_file(output_path, as_attachment=True)

# Plans route (FIXED syntax)
@app.route("/plans")
def plans():
    return "<h2>Subscription plans (placeholder)</h2>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
