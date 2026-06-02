"""Escriba — FastAPI app with live (SSE) streaming transcription.

Routes:
    GET  /                       -> the web UI
    GET  /api/config             -> {consent, telemetry_configured, transcriptions, minutes}
    POST /api/consent            -> record the user's choice (agree=true/false)
    POST /api/transcribe         -> validate, save temp file, start job -> {job_id}
    GET  /api/stream/{job_id}    -> Server-Sent Events: live segments + progress + done
    POST /api/cancel/{job_id}    -> stop a running job early
    GET  /api/result/{job_id}    -> final aligned segments
    GET  /api/export/{job_id}    -> download (?fmt=txt|srt|vtt|json)
"""

from __future__ import annotations

import asyncio
import json
import queue
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse

from .config import ACCEPTED_EXT, MAX_FILE_BYTES, WORKDIR, WEB_DIR
from .pipeline import run_pipeline
from . import exports, telemetry, storage

app = FastAPI(title="Escriba", description="Local timestamped transcription")

JOBS: dict[str, dict] = {}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------- config/consent
@app.get("/api/config")
def get_config():
    stats = telemetry.public_stats()
    cfg = telemetry.get_config()
    stats["output_folder"] = cfg.get("output_folder", "")
    return stats


@app.post("/api/consent")
def consent(agree: bool = Form(...)):
    telemetry.set_consent(agree)
    return telemetry.public_stats()


@app.post("/api/output-folder")
def set_output_folder(path: str = Form("")):
    p = (path or "").strip()
    cfg = telemetry.get_config()
    if p:
        folder = Path(p).expanduser()
        if not folder.is_dir():
            raise HTTPException(400, "That folder doesn't exist on this computer.")
        cfg["output_folder"] = str(folder)
    else:
        cfg["output_folder"] = ""                              # clear it
    telemetry._save(cfg)
    return {"output_folder": cfg["output_folder"]}


# ---------------------------------------------------------------- history
@app.get("/api/history")
def history():
    return {"items": storage.list_transcripts()}


@app.get("/api/history/{transcript_id}/{fmt}")
def history_export(transcript_id: str, fmt: Literal["txt", "srt", "vtt", "json"] = "txt"):
    text = storage.read_format(transcript_id, fmt)
    if text is None:
        raise HTTPException(404, "Not found.")
    media = "application/json" if fmt == "json" else "text/plain"
    return PlainTextResponse(
        text, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="transcript.{fmt}"'},
    )


# ---------------------------------------------------------------- transcribe
@app.post("/api/transcribe")
async def transcribe(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    mode: Literal["standard", "fast"] = Form("standard"),
    language: Literal["auto", "es", "en"] = Form("auto"),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ACCEPTED_EXT:                                  # [GUARDRAIL]
        raise HTTPException(415, "That file type isn't supported. Try MP3, WAV, M4A, or MP4.")

    job_id = uuid.uuid4().hex
    raw_path = WORKDIR / f"{job_id}{ext}"

    size = 0
    with raw_path.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_BYTES:                            # [GUARDRAIL]
                out.close()
                raw_path.unlink(missing_ok=True)
                raise HTTPException(413, "That file is too large.")
            out.write(chunk)

    job = {"status": "working", "segments": None, "language": None, "minutes": 0,
           "error": None, "cancel": False, "queue": queue.Queue(),
           "name": file.filename or "transcript"}
    JOBS[job_id] = job
    background.add_task(run_pipeline, job, raw_path, mode, language)
    return {"job_id": job_id}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/api/stream/{job_id}")
async def stream(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job.")

    async def event_gen():
        q: queue.Queue = job["queue"]
        # tiny hello so the browser opens the stream immediately
        yield _sse({"type": "open"})
        while True:
            try:
                ev = q.get_nowait()
                yield _sse(ev)
                if ev["type"] in ("done", "error", "cancelled"):
                    return
            except queue.Empty:
                # reconnect / already-finished case: emit a terminal event and stop
                if job["status"] in ("done", "error", "cancelled"):
                    yield _sse({"type": job["status"], "progress": 100,
                                "message": job.get("error")})
                    return
                await asyncio.sleep(0.08)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )


@app.post("/api/cancel/{job_id}")
def cancel(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job.")
    job["cancel"] = True
    return {"ok": True}


@app.get("/api/result/{job_id}")
def result(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job.")
    if job["status"] != "done":
        raise HTTPException(409, "Not finished yet.")
    return {"segments": job["segments"], "language": job["language"],
            "minutes": job["minutes"]}


@app.get("/api/export/{job_id}")
def export(job_id: str, fmt: Literal["txt", "srt", "vtt", "json"] = "txt"):
    job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404, "No finished transcript for that job.")
    segs = job["segments"]
    if fmt == "json":
        return JSONResponse(content={"tool": "Escriba", "model": "whisperx",
                                     "language": job["language"], "segments": segs})
    text = exports.BUILDERS[fmt](segs)
    return PlainTextResponse(
        text, headers={"Content-Disposition": f'attachment; filename="transcript.{fmt}"'}
    )
