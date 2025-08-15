from flask import Flask, render_template, request, send_file, redirect, url_for
import os
from highlight_feature import process_files  # yeh tumhara existing function hona chahiye
import uuid

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html', user=None, is_subscribed=False)

@app.route('/highlight', methods=['POST'])
def highlight_route():
    pdf_file = request.files['pdf_file']
    excel_file = request.files['excel_file']
    highlight_type = request.form.get('highlight_type')

    if not pdf_file or not excel_file:
        return "Missing files", 400

    # Save uploaded files
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{pdf_file.filename}")
    excel_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{excel_file.filename}")
    pdf_file.save(pdf_path)
    excel_file.save(excel_path)

    # Output folder for this task
    task_output_folder = os.path.join(app.config['OUTPUT_FOLDER'], str(uuid.uuid4()))
    os.makedirs(task_output_folder, exist_ok=True)

    # Call your existing highlight function
    process_files(pdf_path, excel_path, task_output_folder, highlight_type=highlight_type)

    # Assuming your process_files saves 'highlighted.pdf'
    output_pdf = os.path.join(task_output_folder, "highlighted.pdf")
    return send_file(output_pdf, as_attachment=True)

@app.route('/plans')
def plans():
    return "<h1>Plans Page</h1>"

@app.route('/about')
def about():
    return "<h1>About Page</h1>"

if __name__ == "__main__":
    app.run(debug=True)
