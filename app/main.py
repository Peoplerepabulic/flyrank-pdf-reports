"""Report API (BE-08).

- POST /reports      -> generate the sales PDF (201 {id, file_url})
- GET  /reports/{id} -> report record, or 404
- GET  /reports/{id}/file -> the PDF bytes, or 404 (file served as a
  download; the JSON record carries only the link, never the bytes)

Idempotency: the report payload is hashed (SHA-256 over canonical JSON).
A repeat POST with identical data returns the EXISTING report id instead
of generating a second PDF — rapid double-clicks create exactly one file.
"""
import hashlib
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from .analytics import getReportData
from .db import REPORTS_DIR, get_conn, init_db
from .render import build_html, render_pdf


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    os.makedirs(REPORTS_DIR, exist_ok=True)
    yield


app = FastAPI(title="PDF Report Generator", lifespan=lifespan)


def _payload_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _record_to_json(row) -> dict:
    return {
        "id": row["id"],
        "hash": row["hash"],
        "file_url": f"/reports/{row['id']}/file",
        "created_at": row["created_at"],
    }


@app.post("/reports", status_code=201)
def create_report():
    data = getReportData()
    digest = _payload_hash(data)
    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT id, hash, path, created_at FROM reports WHERE hash = ?",
            (digest,),
        ).fetchone()
        if existing is not None:
            # Idempotent replay: same data -> same report, no new file.
            return JSONResponse(status_code=200, content=_record_to_json(existing))
        now = datetime.now(timezone.utc).isoformat()
        html = build_html(data, generated_at=now)
        # insert first to reserve the id, then render to a stable filename
        cur = conn.execute(
            "INSERT INTO reports (hash, path, created_at) VALUES (?, ?, ?)",
            (digest, "pending", now),
        )
        report_id = cur.lastrowid
        path = os.path.join(REPORTS_DIR, f"report_{report_id}.pdf")
        render_pdf(html, path)
        conn.execute("UPDATE reports SET path = ? WHERE id = ?", (path, report_id))
        conn.commit()
        row = conn.execute(
            "SELECT id, hash, path, created_at FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        return JSONResponse(status_code=201, content=_record_to_json(row))
    finally:
        conn.close()


@app.get("/reports/{report_id}")
def get_report(report_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, hash, path, created_at FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return JSONResponse(status_code=404, content={"error": "Report not found"})
    return _record_to_json(row)


@app.get("/reports/{report_id}/file")
def download_report(report_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT path FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None or not os.path.exists(row["path"]):
        return JSONResponse(status_code=404, content={"error": "Report not found"})
    return FileResponse(row["path"], media_type="application/pdf",
                        filename=f"report_{report_id}.pdf")
