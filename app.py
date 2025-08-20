from flask import Flask, render_template, request, send_file, redirect, url_for, flash
import os
import warnings
from werkzeug.utils import secure_filename
from highlight_feature import highlight_pdf

# Flask app setup
app = Flask(__name__)
app.secret_key = "supersecretkey"

# File storage folders
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)


def clear_uploads():
    """Remove all uploaded and result files"""
    for folder in [UPLOAD_FOLDER, RESULTS_FOLDER]:
        for f in os.listdir(folder):
            os.remove(os.path.join(folder, f))


@app.route("/", methods=["GET", "POST"])
def index():
    output_pdf = None
    not_found_excel = None

    if request.method == "POST":
        if request.form.get("action") == "refresh":
            clear_uploads()
            flash("Uploads and results cleared. Ready for new task.")
            return redirect(url_for("index"))

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

    return render_template("index.html", output_pdf=output_pdf, not_found_excel=not_found_excel)


@app.route("/download/<filename>")
def download_file(filename):
    return send_file(os.path.join(RESULTS_FOLDER, filename), as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
