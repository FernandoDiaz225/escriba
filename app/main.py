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
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse, FileResponse

from .config import ACCEPTED_EXT, MAX_FILE_BYTES, WORKDIR, WEB_DIR, WORKSPACE_DIR
from .pipeline import run_pipeline
from . import exports, telemetry, storage, audio

app = FastAPI(title="Escriba", description="Local timestamped transcription")

JOBS: dict[str, dict] = {}

# token -> Path, for transient audio files we serve back to the browser
WORKSPACE: dict[str, Path] = {}


async def _save_upload(file: UploadFile, dest: Path) -> Path:
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "That file is too large.")
            out.write(chunk)
    return dest


def _stash(path: Path) -> str:
    token = uuid.uuid4().hex
    WORKSPACE[token] = path
    return token


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


# ============================================================================
#  Serve transient audio back to the browser (join results, master previews)
# ============================================================================
@app.get("/api/audio/{token}")
def serve_audio(token: str):
    path = WORKSPACE.get(token)
    if not path or not path.is_file():
        raise HTTPException(404, "Audio not found.")
    media = "audio/mpeg" if path.suffix == ".mp3" else "audio/wav"
    return FileResponse(str(path), media_type=media)


def _ext_ok(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in ACCEPTED_EXT:
        raise HTTPException(415, "Unsupported file type. Try MP3, WAV, M4A, or MP4.")
    return ext


# ============================================================================
#  PREPARE station — join Side A + B and/or light clean for transcription
# ============================================================================
@app.post("/api/prepare")
async def prepare(
    file_a: UploadFile = File(...),
    file_b: UploadFile | None = File(None),
    clean: bool = Form(True),
):
    ext_a = _ext_ok(file_a.filename)
    uid = uuid.uuid4().hex
    a_path = await _save_upload(file_a, WORKSPACE_DIR / f"{uid}_a{ext_a}")

    try:
        if file_b is not None and file_b.filename:
            ext_b = _ext_ok(file_b.filename)
            b_path = await _save_upload(file_b, WORKSPACE_DIR / f"{uid}_b{ext_b}")
            current = audio.join_sides(a_path, b_path, WORKSPACE_DIR / f"{uid}_joined")
        else:
            current = a_path

        if clean:
            current = audio.prep_for_transcription(current, WORKSPACE_DIR / f"{uid}_prepped")

        token = _stash(current)
        return {"token": token, "url": f"/api/audio/{token}",
                "duration": round(audio.probe_seconds(current), 1),
                "joined": bool(file_b and file_b.filename), "cleaned": clean}
    except Exception as e:
        raise HTTPException(500, f"Audio prep failed: {e}")


@app.post("/api/transcribe-token")
async def transcribe_token(
    background: BackgroundTasks,
    token: str = Form(...),
    mode: str = Form("standard"),
    language: str = Form("auto"),
    name: str = Form("prepared-audio"),
):
    """Transcribe a file that's already in the workspace (e.g. from Prepare)."""
    src = WORKSPACE.get(token)
    if not src or not src.is_file():
        raise HTTPException(404, "That prepared audio is no longer available.")
    job_id = uuid.uuid4().hex
    raw_path = WORKDIR / f"{job_id}.wav"
    import shutil
    shutil.copy2(src, raw_path)
    job = {"status": "working", "segments": None, "language": None, "minutes": 0,
           "error": None, "cancel": False, "queue": __import__("queue").Queue(), "name": name}
    JOBS[job_id] = job
    background.add_task(run_pipeline, job, raw_path, mode, language)
    return {"job_id": job_id}


# ============================================================================
#  MASTER station — human-in-the-loop listening restoration (SoX)
# ============================================================================
@app.post("/api/master/upload")
async def master_upload(file: UploadFile = File(...)):
    ext = _ext_ok(file.filename)
    uid = uuid.uuid4().hex
    src = await _save_upload(file, WORKSPACE_DIR / f"{uid}_src{ext}")
    token = _stash(src)
    return {"token": token, "url": f"/api/audio/{token}", "name": file.filename,
            "duration": round(audio.probe_seconds(src), 1),
            "sox": audio.have("sox")}


def _render_master(token, start, end, amount, highpass, dehum, gentle):
    src = WORKSPACE.get(token)
    if not src or not src.is_file():
        raise HTTPException(404, "That audio is no longer available.")
    uid = uuid.uuid4().hex
    prof = WORKSPACE_DIR / f"{uid}.prof"
    try:
        audio.make_noise_profile(src, start, end, prof)
        out = audio.restore_master(src, prof, WORKSPACE_DIR / f"{uid}_master",
                                   amount=amount, highpass=highpass,
                                   dehum=dehum, gentle=gentle)
        return out
    except RuntimeError as e:                 # SoX missing
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Restoration failed: {e}")
    finally:
        prof.unlink(missing_ok=True)


@app.post("/api/master/preview")
def master_preview(token: str = Form(...), start: float = Form(...), end: float = Form(...),
                   amount: float = Form(0.21), highpass: int = Form(60),
                   dehum: bool = Form(True), gentle: bool = Form(False)):
    out = _render_master(token, start, end, amount, highpass, dehum, gentle)
    t = _stash(out)
    return {"url": f"/api/audio/{t}"}


@app.post("/api/master/save")
def master_save(token: str = Form(...), start: float = Form(...), end: float = Form(...),
                amount: float = Form(0.21), highpass: int = Form(60),
                dehum: bool = Form(True), gentle: bool = Form(False), name: str = Form("master")):
    out = _render_master(token, start, end, amount, highpass, dehum, gentle)
    mp3 = audio.to_mp3(out, out.with_suffix(".mp3"))
    cfg = telemetry.get_config()
    of = cfg.get("output_folder") or ""
    rec = storage.save_master(name, out, mp3,
                              {"amount": amount, "highpass": highpass,
                               "dehum": dehum, "gentle": gentle},
                              Path(of) if of else None)
    return rec


# ============================================================================
#  AUDIT + LIBRARY
# ============================================================================
@app.post("/api/audit")
def audit(name: str = Form(...), tag: str = Form(...), note: str = Form("")):
    return storage.add_audit(name, tag, note)


@app.get("/api/audits")
def audits():
    return {"items": storage.list_audits()}


@app.get("/api/masters")
def masters():
    return {"items": storage.list_masters()}


@app.get("/api/masters/{master_id}/{fmt}")
def master_download(master_id: str, fmt: str):
    if fmt not in ("wav", "mp3"):
        raise HTTPException(400, "bad format")
    f = storage.master_file(master_id, fmt)
    if not f:
        raise HTTPException(404, "Not found.")
    media = "audio/mpeg" if fmt == "mp3" else "audio/wav"
    return FileResponse(str(f), media_type=media,
                        headers={"Content-Disposition": f'attachment; filename="master.{fmt}"'})


@app.post("/api/history/{transcript_id}/tag")
def tag_transcript(transcript_id: str, quality: str = Form(...), note: str = Form("")):
    ok = storage.tag_transcript(transcript_id, quality, note)
    if not ok:
        raise HTTPException(404, "Not found.")
    return {"ok": True}
