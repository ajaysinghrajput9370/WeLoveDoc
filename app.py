import os import uuid import zipfile from datetime import datetime from pathlib import Path

from flask import ( Flask, render_template, request, send_file, jsonify, redirect, url_for, flash, after_this_request, ) from werkzeug.utils import secure_filename from werkzeug.exceptions import HTTPException from flask_cors import CORS

--- Import your processing functions from highlight.py ---

Expected functions (adjust names if your file uses different ones):

pf_process(input_path: str, output_dir: str) -> str | list[str]

esic_process(input_path: str, output_dir: str) -> str | list[str]

try: from highlight import pf_process, esic_process except Exception as e: # Soft-fail import to help with first run; real errors will surface on call pf_process = None esic_process = None

----------------------------------------------------------------------------

App configuration

----------------------------------------------------------------------------

BASE_DIR = Path(file).resolve().parent UPLOAD_DIR = BASE_DIR / "uploads" OUTPUT_DIR = BASE_DIR / "outputs" UPLOAD_DIR.mkdir(exist_ok=True) OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_EXT = {"pdf", "xls", "xlsx"}

app = Flask(name, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static")) CORS(app)

Use env var if provided; otherwise a safe default for dev

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-prod-" + uuid.uuid4().hex) app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit

----------------------------------------------------------------------------

Helpers

----------------------------------------------------------------------------

def allowed_file(filename: str) -> bool: return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def _unique_stem(prefix: str = "job") -> str: return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

def _zip_outputs(files, zip_path: Path) -> Path: with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf: for f in files: f = Path(f) if f.exists(): zf.write(f, arcname=f.name) return zip_path

----------------------------------------------------------------------------

Routes: Pages

----------------------------------------------------------------------------

@app.route("/") def home(): return render_template("index.html")

@app.route("/about") def about(): return render_template("about.html")

@app.route("/terms") def terms(): return render_template("terms.html")

@app.route("/health") def health(): return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})

----------------------------------------------------------------------------

Routes: Processing APIs

----------------------------------------------------------------------------

@app.post("/process/pf") def process_pf(): if pf_process is None: return jsonify({"ok": False, "error": "pf_process not available. Check highlight.py import."}), 500

if "file" not in request.files:
    return jsonify({"ok": False, "error": "No file part in request."}), 400

file = request.files["file"]
if file.filename == "":
    return jsonify({"ok": False, "error": "No selected file."}), 400

if not allowed_file(file.filename):
    return jsonify({"ok": False, "error": f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXT))}"}), 400

job_id = _unique_stem("pf")
job_upload_dir = UPLOAD_DIR / job_id
job_output_dir = OUTPUT_DIR / job_id
job_upload_dir.mkdir(parents=True, exist_ok=True)
job_output_dir.mkdir(parents=True, exist_ok=True)

filename = secure_filename(file.filename)
input_path = job_upload_dir / filename
file.save(input_path)

try:
    result = pf_process(str(input_path), str(job_output_dir))
    # result may be a single path or a list of paths
    if isinstance(result, (list, tuple)):
        paths = [Path(p) for p in result]
    else:
        paths = [Path(result)]

    # If single file, stream it. If multiple, zip them.
    if len(paths) == 1 and paths[0].exists():
        out_path = paths[0]
        @after_this_request
        def cleanup(response):  # noqa: ANN001
            try:
                # Optional: keep outputs; if you want auto-delete, uncomment below
                # for p in [input_path, *paths]:
                #     if p.exists():
                #         p.unlink(missing_ok=True)
                pass
            except Exception:
                pass
            return response

        return send_file(out_path, as_attachment=True, download_name=out_path.name)
    else:
        zip_path = job_output_dir / f"{job_id}.zip"
        _zip_outputs(paths, zip_path)

        @after_this_request
        def cleanup_zip(response):  # noqa: ANN001
            try:
                # Optional: see cleanup note above
                pass
            except Exception:
                pass
            return response

        return send_file(zip_path, as_attachment=True, download_name=zip_path.name)

except Exception as e:  # surface processing issues clearly
    return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/process/esic") def process_esic(): if esic_process is None: return jsonify({"ok": False, "error": "esic_process not available. Check highlight.py import."}), 500

if "file" not in request.files:
    return jsonify({"ok": False, "error": "No file part in request."}), 400

file = request.files["file"]
if file.filename == "":
    return jsonify({"ok": False, "error": "No selected file."}), 400

if not allowed_file(file.filename):
    return jsonify({"ok": False, "error": f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXT))}"}), 400

job_id = _unique_stem("esic")
job_upload_dir = UPLOAD_DIR / job_id
job_output_dir = OUTPUT_DIR / job_id
job_upload_dir.mkdir(parents=True, exist_ok=True)
job_output_dir.mkdir(parents=True, exist_ok=True)

filename = secure_filename(file.filename)
input_path = job_upload_dir / filename
file.save(input_path)

try:
    result = esic_process(str(input_path), str(job_output_dir))
    if isinstance(result, (list, tuple)):
        paths = [Path(p) for p in result]
    else:
        paths = [Path(result)]

    if len(paths) == 1 and paths[0].exists():
        out_path = paths[0]
        return send_file(out_path, as_attachment=True, download_name=out_path.name)
    else:
        zip_path = job_output_dir / f"{job_id}.zip"
        _zip_outputs(paths, zip_path)
        return send_file(zip_path, as_attachment=True, download_name=zip_path.name)

except Exception as e:
    return jsonify({"ok": False, "error": str(e)}), 500

----------------------------------------------------------------------------

Optional: Generic upload + choose process from form (index.html)

----------------------------------------------------------------------------

@app.post("/process") def process_from_form(): """Handle a form with fields: file (File), process_type (pf|esic).""" process_type = request.form.get("process_type", "pf").lower() file = request.files.get("file")

if not file or file.filename == "":
    flash("Please select a file to upload.", "error")
    return redirect(url_for("home"))

if not allowed_file(file.filename):
    flash(f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXT))}", "error")
    return redirect(url_for("home"))

# Re-post to the API routes to keep logic in one place
with app.test_client() as client:
    data = {"file": (file.stream, secure_filename(file.filename))}
    if process_type == "esic":
        resp = client.post("/process/esic", data=data, content_type="multipart/form-data")
    else:
        resp = client.post("/process/pf", data=data, content_type="multipart/form-data")

# If API returned a file, stream it directly
if resp.status_code == 200 and resp.headers.get("Content-Disposition", "").startswith("attachment;"):
    # Save API response to a temp file and re-send
    job_id = _unique_stem("dl")
    dl_path = OUTPUT_DIR / f"{job_id}.bin"
    with open(dl_path, "wb") as f:
        f.write(resp.data)
    return send_file(dl_path, as_attachment=True, download_name=resp.headers.get("Content-Disposition").split("filename=")[-1].strip("\"") or dl_path.name)

# Otherwise show error on the home page
try:
    payload = resp.get_json(silent=True) or {}
    error = payload.get("error") or f"Processing failed (status {resp.status_code})."
except Exception:
    error = f"Processing failed (status {resp.status_code})."

flash(error, "error")
return redirect(url_for("home"))

----------------------------------------------------------------------------

Error handlers

----------------------------------------------------------------------------

@app.errorhandler(HTTPException) def handle_http_error(e: HTTPException): if request.path.startswith("/process") or request.accept_mimetypes.best == "application/json": return jsonify({"ok": False, "error": e.name, "code": e.code}), e.code return render_template("error.html", error=e), e.code

@app.errorhandler(Exception) def handle_generic_error(e: Exception): # Avoid leaking internals on HTML; include message for JSON if request.path.startswith("/process") or request.accept_mimetypes.best == "application/json": return jsonify({"ok": False, "error": str(e)}), 500 return render_template("error.html", error=e), 500

----------------------------------------------------------------------------

Entry

----------------------------------------------------------------------------

if name == "main": # Host/port can be overridden by environment (useful for deployment) host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0") port = int(os.environ.get("FLASK_RUN_PORT", "5000")) debug = os.environ.get("FLASK_DEBUG", "0") == "1"

app.run(host=host, port=port, debug=debug)

