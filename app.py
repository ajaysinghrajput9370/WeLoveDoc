from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import os
import uuid
from werkzeug.utils import secure_filename
from highlight import process_files  # Tumhara existing highlight logic

app = Flask(__name__)
app.secret_key = "sOUMU"

UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

@app.route("/", methods=["GET"])
def index():
    user = session.get("email")
    return render_template("index.html", user=user, tasks_done=0, is_subscribed=True)

@app.route("/highlight", methods=["POST"])
def highlight_route():
    if "pdf_file" not in request.files or "excel_file" not in request.files:
        flash("Please select both PDF and Excel files", "danger")
        return redirect(url_for("index"))

    pdf_file = request.files["pdf_file"]
    excel_file = request.files["excel_file"]
    highlight_type = request.form.get("highlight_type")

    if pdf_file.filename.strip() == "" or excel_file.filename.strip() == "":
        flash("Invalid file selection", "danger")
        return redirect(url_for("index"))

    pdf_path = os.path.join(UPLOAD_FOLDER, secure_filename(pdf_file.filename))
    excel_path = os.path.join(UPLOAD_FOLDER, secure_filename(excel_file.filename))
    pdf_file.save(pdf_path)
    excel_file.save(excel_path)

    # Output unique file names
    out_pdf_name = f"{uuid.uuid4().hex}.pdf"
    not_found_excel_name = f"{uuid.uuid4().hex}.xlsx"

    out_pdf_path = os.path.join(RESULT_FOLDER, out_pdf_name)
    not_found_excel_path = os.path.join(RESULT_FOLDER, not_found_excel_name)

    # Process using your highlight.py
    process_files(pdf_path, excel_path, highlight_type, out_pdf_path, not_found_excel_path)

    return render_template(
        "result.html",
        out_pdf=out_pdf_name if os.path.exists(out_pdf_path) else None,
        not_found_excel=not_found_excel_name if os.path.exists(not_found_excel_path) else None
    )

@app.route("/download/pdf")
def download_pdf():
    file = request.args.get("file")
    path = os.path.join(RESULT_FOLDER, file)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    else:
        flash("PDF file not found", "danger")
        return redirect(url_for("index"))

@app.route("/download/excel")
def download_excel():
    file = request.args.get("file")
    path = os.path.join(RESULT_FOLDER, file)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    else:
        flash("Excel file not found", "danger")
        return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
