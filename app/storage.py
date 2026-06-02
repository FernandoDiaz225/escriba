"""Transcript storage — so work is never lost.

Every finished transcript is written to a permanent local library
(~/.escriba/transcripts/). If the user has set an output folder, a copy also
goes there — point that at a Google Drive / Dropbox SYNC folder and the whole
team gets the transcript automatically, with no accounts or server involved.

A small meta.json in each transcript folder powers the in-app history list.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import TRANSCRIPTS_DIR, CONFIG_PATH, MASTERS_DIR, AUDITS_PATH
from . import exports


def _slug(name: str) -> str:
    base = re.sub(r"\.[^.]+$", "", name or "transcript")     # drop extension
    base = re.sub(r"[^\w\-]+", "-", base).strip("-").lower()
    return base[:48] or "transcript"


def _write_all_formats(folder: Path, segments, language: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "transcript.txt").write_text(exports.to_txt(segments), encoding="utf-8")
    (folder / "transcript.srt").write_text(exports.to_srt(segments), encoding="utf-8")
    (folder / "transcript.vtt").write_text(exports.to_vtt(segments), encoding="utf-8")
    (folder / "transcript.json").write_text(exports.to_json(segments, language), encoding="utf-8")


def _output_folder() -> Path | None:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        p = (cfg.get("output_folder") or "").strip()
        return Path(p) if p else None
    except Exception:
        return None


def save_transcript(name: str, segments, language: str, minutes: float) -> dict:
    """Write a transcript to the permanent library (+ optional shared folder).
    Returns a metadata record. Never raises — saving must not break a good job."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    folder = TRANSCRIPTS_DIR / f"{ts}-{_slug(name)}"
    record = {
        "id": folder.name,
        "name": name or "transcript",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "language": language,
        "segments": len(segments),
        "minutes": round(minutes or 0, 2),
        "dir": str(folder),
        "saved_to_output": None,
    }
    try:
        _write_all_formats(folder, segments, language)

        # extra copy into the user's chosen (possibly cloud-synced) folder
        out = _output_folder()
        if out:
            try:
                dest = out / folder.name
                _write_all_formats(dest, segments, language)
                record["saved_to_output"] = str(dest)
            except Exception:
                record["saved_to_output"] = "error"

        (folder / "meta.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    except Exception:
        pass
    return record


def list_transcripts(limit: int = 100) -> list[dict]:
    items = []
    if not TRANSCRIPTS_DIR.exists():
        return items
    for folder in sorted(TRANSCRIPTS_DIR.iterdir(), reverse=True):
        meta = folder / "meta.json"
        if meta.is_file():
            try:
                items.append(json.loads(meta.read_text(encoding="utf-8")))
            except Exception:
                continue
        if len(items) >= limit:
            break
    return items


def read_format(transcript_id: str, fmt: str) -> str | None:
    """Return the saved text of one format for a past transcript."""
    safe = re.sub(r"[^\w\-]+", "", transcript_id)            # no path traversal
    f = TRANSCRIPTS_DIR / safe / f"transcript.{fmt}"
    if f.is_file():
        try:
            return f.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


# ==========================================================================
#  Tape audits — quick quality tags so bad tapes get caught before work
# ==========================================================================
def add_audit(name: str, tag: str, note: str) -> dict:
    rec = {
        "id": time.strftime("%Y%m%d-%H%M%S"),
        "name": name or "tape",
        "tag": tag,
        "note": note or "",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        items = list_audits()
        items.insert(0, rec)
        AUDITS_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")
    except Exception:
        pass
    return rec


def list_audits() -> list[dict]:
    try:
        return json.loads(AUDITS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


# ==========================================================================
#  Listening masters — saved restored audio (wav + mp3) with metadata
# ==========================================================================
def save_master(name: str, wav_path: Path, mp3_path: Path,
                settings: dict, output_folder: Path | None) -> dict:
    ts = time.strftime("%Y%m%d-%H%M%S")
    folder = MASTERS_DIR / f"{ts}-{_slug(name)}"
    record = {
        "id": folder.name,
        "name": name or "master",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settings": settings,
        "dir": str(folder),
        "saved_to_output": None,
    }
    try:
        folder.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(wav_path, folder / "master.wav")
        shutil.copy2(mp3_path, folder / "master.mp3")
        if output_folder:
            try:
                dest = output_folder / folder.name
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(wav_path, dest / "master.wav")
                shutil.copy2(mp3_path, dest / "master.mp3")
                record["saved_to_output"] = str(dest)
            except Exception:
                record["saved_to_output"] = "error"
        (folder / "meta.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    except Exception:
        pass
    return record


def list_masters(limit: int = 100) -> list[dict]:
    items = []
    if not MASTERS_DIR.exists():
        return items
    for folder in sorted(MASTERS_DIR.iterdir(), reverse=True):
        meta = folder / "meta.json"
        if meta.is_file():
            try:
                items.append(json.loads(meta.read_text(encoding="utf-8")))
            except Exception:
                continue
        if len(items) >= limit:
            break
    return items


def master_file(master_id: str, fmt: str) -> Path | None:
    safe = re.sub(r"[^\w\-]+", "", master_id)
    f = MASTERS_DIR / safe / f"master.{fmt}"
    return f if f.is_file() else None


def tag_transcript(transcript_id: str, quality: str, note: str) -> bool:
    """Attach an audit tag to a saved transcript's meta.json."""
    safe = re.sub(r"[^\w\-]+", "", transcript_id)
    meta = TRANSCRIPTS_DIR / safe / "meta.json"
    if not meta.is_file():
        return False
    try:
        rec = json.loads(meta.read_text(encoding="utf-8"))
        rec["quality"] = quality
        rec["note"] = note or ""
        meta.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False
