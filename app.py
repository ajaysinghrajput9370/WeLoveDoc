from flask import Flask, render_template, request, send_file
import os
from highlight_feature import process_files  # Make sure this module exists

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Home page
@app.route("/")
def index():
    return render_template("index.html", is_subscribed=False)

# Highlight route
@app.route("/highlight", methods=["POST"])
def highlight_route():
    # Check if files are present in the request
    if 'pdf_file' not in request.files or 'excel_file' not in request.files:
        return "Missing PDF or Excel file", 400
    
    pdf_file = request.files["pdf_file"]
    excel_file = request.files["excel_file"]
    
    # Check if files have names
    if pdf_file.filename == '' or excel_file.filename == '':
        return "No selected file", 400
    
    highlight_type = request.form.get("highlight_type", "uan")

    # Save uploaded files
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_file.filename)
    excel_path = os.path.join(app.config['UPLOAD_FOLDER'], excel_file.filename)
    
    pdf_file.save(pdf_path)
    excel_file.save(excel_path)

    # Process files
    try:
        output_path = process_files(pdf_path, excel_path, highlight_type)
        return send_file(output_path, as_attachment=True)
    except Exception as e:
        return f"Error processing files: {str(e)}", 500
    finally:
        # Clean up: remove uploaded files
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(excel_path):
            os.remove(excel_path)

# Plans route
@app.route("/plans")
def plans():
    return "<h2>Subscription plans (placeholder)</h2>"

# About route
@app.route("/about")
def about():
    return render_template("about.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
