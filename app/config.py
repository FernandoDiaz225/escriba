"""Central configuration and guardrail constants for Escriba."""

import os
import tempfile
from pathlib import Path

APP_VERSION = "0.2.0"

# Accepted upload types — re-checked on the server even though the UI checks too.
ACCEPTED_EXT = {".mp3", ".wav", ".m4a", ".mp4", ".aac", ".flac", ".ogg"}

# [GUARDRAIL] cheap ceilings that stop one bad file from causing big problems.
MAX_FILE_BYTES = 1_500 * 1024 * 1024     # ~1.5 GB upload cap
MAX_SECONDS = 4 * 60 * 60                # 4-hour duration cap (matches UI copy)

# Whisper model size. "small" is a sensible CPU default; "medium"/"large-v2"
# are more accurate but slower (or need an NVIDIA GPU).
MODEL_SIZE = "small"
BEAM_SIZE = 5

# Temp working dir. Uploads live here only while a job runs, then are deleted.
WORKDIR = Path(tempfile.gettempdir()) / "escriba"
WORKDIR.mkdir(exist_ok=True)

# Frontend location (served at "/").
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# --- usage / telemetry -------------------------------------------------------
# A small per-user config file (anonymous install id + local counters + consent)
# lives in the user's home dir, NOT in the project, so it survives reinstalls.
CONFIG_DIR = Path.home() / ".escriba"
CONFIG_DIR.mkdir(exist_ok=True)
CONFIG_PATH = CONFIG_DIR / "config.json"

# Where anonymous usage pings go. EMPTY BY DEFAULT = telemetry fully disabled.
# Set this env var to your deployed endpoint (see telemetry-server/) to enable.
TELEMETRY_URL = os.environ.get("ESCRIBA_TELEMETRY_URL", "").strip()
TELEMETRY_KEY = os.environ.get("ESCRIBA_TELEMETRY_KEY", "escriba-public").strip()

# Where finished transcripts are auto-saved (so they're never lost). This is a
# permanent local library; the optional "output folder" below is an extra copy.
TRANSCRIPTS_DIR = CONFIG_DIR / "transcripts"
TRANSCRIPTS_DIR.mkdir(exist_ok=True)

# Listening masters and tape audits (the platform stations beyond transcription).
MASTERS_DIR = CONFIG_DIR / "masters"
MASTERS_DIR.mkdir(exist_ok=True)
AUDITS_PATH = CONFIG_DIR / "audits.json"

# Transient audio files served back to the browser (join results, master previews).
WORKSPACE_DIR = WORKDIR / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
