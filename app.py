from flask import Flask, render_template, request, send_from_directory
import os

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['UPLOAD_FOLDER'] = "uploads"

@app.route("/")
def index():
    return render_template("index.html")

# example upload handler (adjust per your highlight code)
@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f:
        return "No file", 400
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    path = os.path.join(app.config['UPLOAD_FOLDER'], f.filename)
    f.save(path)
    # call your processing function here
    return f"Saved {f.filename}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
