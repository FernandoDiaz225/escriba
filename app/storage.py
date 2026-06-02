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

from .config import TRANSCRIPTS_DIR, CONFIG_PATH
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
