"""Anonymous usage tracking + a local counter.

Two separate things live here:

1. A LOCAL counter (always on, never leaves the machine) so the user can see
   their own totals and so you can gather resume numbers just by asking people.

2. An optional ANONYMOUS ping to a central endpoint, sent ONLY when (a) the user
   has consented and (b) you've configured a telemetry URL. It contains only:
       install_id  – a random anonymous UUID (no name, no IP collected by us)
       event       – the string "transcription_complete"
       minutes     – how many minutes of audio were processed
       version     – the app version
   It NEVER contains audio, transcript text, filenames, or any personal data.
   Whatever you disclose in PRIVACY.md must match exactly this list.
"""

from __future__ import annotations

import json
import threading
import urllib.request
import uuid

from .config import CONFIG_PATH, TELEMETRY_URL, TELEMETRY_KEY, APP_VERSION


def _load() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_config() -> dict:
    """Return the config, creating an anonymous install id on first use."""
    cfg = _load()
    changed = False
    if "install_id" not in cfg:
        cfg["install_id"] = uuid.uuid4().hex      # anonymous, random, local
        changed = True
    cfg.setdefault("consent", None)               # None = not asked yet
    cfg.setdefault("total_transcriptions", 0)
    cfg.setdefault("total_minutes", 0.0)
    if changed:
        _save(cfg)
    return cfg


def set_consent(agree: bool) -> dict:
    cfg = get_config()
    cfg["consent"] = bool(agree)
    _save(cfg)
    return cfg


def public_stats() -> dict:
    cfg = get_config()
    return {
        "consent": cfg["consent"],
        "telemetry_configured": bool(TELEMETRY_URL),
        "transcriptions": cfg["total_transcriptions"],
        "minutes": round(cfg["total_minutes"], 1),
    }


def record_completion(minutes: float) -> None:
    """Called once when a transcription finishes successfully."""
    cfg = get_config()
    cfg["total_transcriptions"] += 1
    cfg["total_minutes"] = round(cfg["total_minutes"] + (minutes or 0), 2)
    _save(cfg)

    # Only phone home if the user agreed AND an endpoint is configured.
    if cfg["consent"] and TELEMETRY_URL:
        threading.Thread(
            target=_send, args=(cfg["install_id"], minutes), daemon=True
        ).start()


def _send(install_id: str, minutes: float) -> None:
    """Fire-and-forget anonymous ping. Failures are swallowed on purpose —
    telemetry must never interrupt or slow down the user's work."""
    payload = json.dumps({
        "install_id": install_id,
        "event": "transcription_complete",
        "minutes": round(minutes or 0, 2),
        "version": APP_VERSION,
    }).encode("utf-8")
    req = urllib.request.Request(
        TELEMETRY_URL, data=payload, method="POST",
        headers={"Content-Type": "application/json", "x-escriba-key": TELEMETRY_KEY},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass
