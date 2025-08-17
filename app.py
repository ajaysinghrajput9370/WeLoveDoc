from flask import Flask, render_template, request, send_file, redirect, url_for, session
import os
from highlight_feature import process_files  # Make sure this module exists

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Required for session (replace with strong key)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🏠 Home page
@app.route("/")
def index():
    user = session.get("user")  # session me user ka naam
    return render_template("index.html", is_subscribed=False, user=user)

# ✍ Highlight route
@app.route("/highlight", methods=["POST"])
def highlight_route():
    if 'pdf_file' not in request.files or 'excel_file' not in request.files:
        return "Missing PDF or Excel file", 400
    
    pdf_file = request.files["pdf_file"]
    excel_file = request.files["excel_file"]
    
    if pdf_file.filename == '' or excel_file.filename == '':
        return "No selected file", 400
    
    highlight_type = request.form.get("highlight_type", "uan")

    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_file.filename)
    excel_path = os.path.join(app.config['UPLOAD_FOLDER'], excel_file.filename)
    
    pdf_file.save(pdf_path)
    excel_file.save(excel_path)

    try:
        output_path = process_files(pdf_path, excel_path, highlight_type)
        return send_file(output_path, as_attachment=True)
    except Exception as e:
        return f"Error processing files: {str(e)}", 500
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(excel_path):
            os.remove(excel_path)

# 💳 Plans route
@app.route("/plans")
def plans():
    return "<h2>Subscription plans (placeholder)</h2>"

# ℹ About route
@app.route("/about")
def about():
    return render_template("about.html")

# 🔑 Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # Dummy check (replace with real DB check later)
        if username and password:
            session["user"] = username  # ✅ string save
            return redirect(url_for("index"))
        return "Invalid credentials", 401
    return render_template("login.html")

# 📝 Signup route
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # Dummy save (later integrate DB)
        session["user"] = username  # ✅ string save
        return redirect(url_for("index"))
    return render_template("signup.html")

# 🚪 Logout route
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
