from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash
import os
from highlight_feature import process_files

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Replace with a strong key

UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER

# Home Page
@app.route("/")
def index():
    user = session.get("user")
    return render_template("index.html", user=user)

# Highlight Feature
@app.route("/highlight", methods=["POST"])
def highlight_route():
    if 'pdf_file' not in request.files or 'excel_file' not in request.files:
        flash("Please upload both PDF and Excel files.", "error")
        return redirect(url_for("index"))

    pdf_file = request.files["pdf_file"]
    excel_file = request.files["excel_file"]

    if pdf_file.filename == '' or excel_file.filename == '':
        flash("No selected file(s).", "error")
        return redirect(url_for("index"))

    highlight_type = request.form.get("highlight_type", "uan")

    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_file.filename)
    excel_path = os.path.join(app.config['UPLOAD_FOLDER'], excel_file.filename)

    pdf_file.save(pdf_path)
    excel_file.save(excel_path)

    try:
        output_files = process_files(pdf_path, excel_path, highlight_type, app.config['RESULTS_FOLDER'])

        if isinstance(output_files, list):
            return send_file(output_files[0], as_attachment=True)
        else:
            return send_file(output_files, as_attachment=True)

    except Exception as e:
        return f"Error processing files: {str(e)}", 500

    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(excel_path):
            os.remove(excel_path)

# Plans
@app.route("/plans")
def plans():
    return "<h2>Subscription plans (Coming Soon)</h2>"

# About
@app.route("/about")
def about():
    return render_template("about.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username and password:
            session["user"] = username
            return redirect(url_for("index"))
        return "Invalid credentials", 401
    return render_template("login.html")

# Signup
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        session["user"] = username
        return redirect(url_for("index"))
    return render_template("signup.html")

# Logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
