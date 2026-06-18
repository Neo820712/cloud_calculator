"""
Flask web application – Cloud Instance Verifier.

Routes:
  GET  /            → HTML UI
  POST /process     → upload Excel + config → returns {job_id}
  GET  /status/<id> → job progress (polling)
  GET  /download/<id> → download result Excel
  GET  /check-deps  → verify Playwright is installed
"""
import io
import os
import sys
import threading
import uuid
import zipfile
from datetime import date

import pandas as pd
from flask import Flask, request, render_template, send_file, jsonify

from excel_processor import process_excel_file, xpa_filename, month_name_es

# Locate the templates folder whether running as script or PyInstaller .exe
if getattr(sys, "frozen", False):
    _BASE = sys._MEIPASS          # PyInstaller unpacks files here at runtime
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(_BASE, "templates"))
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024   # 100 MB

# In-memory job store (single-user local app)
_jobs: dict = {}
_jobs_lock = threading.Lock()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/check-deps")
def check_deps():
    try:
        from playwright.sync_api import sync_playwright   # noqa: F401
        print("[check-deps] Playwright OK")
        return jsonify({"playwright": True})
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        print(f"[check-deps] FALHOU — {msg}")
        return jsonify({"playwright": False, "message": msg})


@app.route("/process", methods=["POST"])
def process():
    try:
        print(f"[process] files={list(request.files.keys())} form={dict(request.form)}")

        if "excel_file" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400

        file = request.files["excel_file"]
        print(f"[process] filename={file.filename!r}")

        link_column      = request.form.get("link_column", "H").strip().upper()
        header_row       = int(request.form.get("header_row", 6))
        cloud_provider   = request.form.get("cloud_provider", "AWS").strip()
        customer_column  = request.form.get("customer_column", "E").strip().upper()
        summarize_by     = request.form.get("summarize_by", "company").strip()

        if summarize_by == "xpa" and not customer_column:
            return jsonify({"error": "O modo Archivos XPA requer a coluna Customer configurada."}), 400

        job_id     = str(uuid.uuid4())
        file_bytes = file.read()
        print(f"[process] {len(file_bytes)} bytes lidos, job_id={job_id}")

        with _jobs_lock:
            _jobs[job_id] = {
                "status":   "running",
                "progress": 0,
                "total":    0,
                "log":      [],
                "result":   None,
                "error":    None,
                "kind":     "xlsx",
            }

        def worker():
            def on_progress(current, total, msg=""):
                with _jobs_lock:
                    _jobs[job_id]["progress"] = current
                    _jobs[job_id]["total"]    = total
                    if msg:
                        _jobs[job_id]["log"].append(msg)

            try:
                result = process_excel_file(
                    file_bytes, link_column, header_row, cloud_provider,
                    customer_column, summarize_by, on_progress
                )

                if summarize_by == "xpa":
                    out = io.BytesIO()
                    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                        for company, df in result.items():
                            buf = io.BytesIO()
                            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                                df.to_excel(writer, index=False, header=False,
                                            sheet_name="Instâncias")
                            buf.seek(0)
                            zf.writestr(xpa_filename(company, date.today()), buf.getvalue())
                    out.seek(0)
                    with _jobs_lock:
                        _jobs[job_id]["result"] = out.getvalue()
                        _jobs[job_id]["kind"]   = "zip"
                        _jobs[job_id]["status"] = "done"
                else:
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine="openpyxl") as writer:
                        result.to_excel(writer, index=False, sheet_name="Instâncias")
                    out.seek(0)
                    with _jobs_lock:
                        _jobs[job_id]["result"] = out.getvalue()
                        _jobs[job_id]["kind"]   = "xlsx"
                        _jobs[job_id]["status"] = "done"
                print(f"[worker] job {job_id} concluído.")
            except Exception as exc:
                import traceback; traceback.print_exc()
                with _jobs_lock:
                    _jobs[job_id]["status"] = "error"
                    _jobs[job_id]["error"]  = str(exc)

        threading.Thread(target=worker, daemon=True).start()
        print(f"[process] worker iniciado, retornando job_id={job_id}")
        return jsonify({"job_id": job_id})

    except Exception as exc:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"Erro interno: {exc}"}), 500


@app.route("/status/<job_id>")
def status(job_id):
    job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job não encontrado"}), 404
    return jsonify({
        "status":   job["status"],
        "progress": job["progress"],
        "total":    job["total"],
        "error":    job.get("error"),
        "log":      job.get("log", [])[-20:],   # last 20 lines
    })


@app.route("/download/<job_id>")
def download(job_id):
    job = _jobs.get(job_id)
    if not job or job["status"] != "done" or not job["result"]:
        return jsonify({"error": "Resultado não disponível"}), 404

    if job.get("kind") == "zip":
        today = date.today()
        return send_file(
            io.BytesIO(job["result"]),
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"archivos_xpa_{today.year}_{month_name_es(today)}.zip",
        )

    return send_file(
        io.BytesIO(job["result"]),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="cloud_instances_verificadas.xlsx",
    )


if __name__ == "__main__":
    print("=" * 55)
    print("  Cloud Instance Verifier")
    print("  Acesse: http://localhost:5000")
    print("=" * 55)
    app.run(debug=False, port=5000, use_reloader=False, threaded=True)
