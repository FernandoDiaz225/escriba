#!/bin/bash
# Escriba — one-time setup for macOS.
# Double-click this file (you may need to right-click > Open the first time).
cd "$(dirname "$0")" || exit 1

echo "============================================"
echo "  Setting up Escriba"
echo "============================================"
echo ""

# 1. Python 3
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ✗ Python 3 isn't installed."
  echo "    Install it from https://www.python.org/downloads/ then run this again."
  echo ""
  read -r -p "  Press Return to close."
  exit 1
fi
echo "  ✓ Python 3 found"

# 2. ffmpeg (install via Homebrew if missing)
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "  • ffmpeg not found — trying to install it…"
  if command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    echo "  ✗ Homebrew isn't installed, so ffmpeg can't be installed automatically."
    echo "    Install Homebrew (https://brew.sh) then run this again."
    echo ""
    read -r -p "  Press Return to close."
    exit 1
  fi
fi
echo "  ✓ ffmpeg found"

# 2b. SoX (for listening-master restoration)
if ! command -v sox >/dev/null 2>&1; then
  echo "  • SoX not found — installing (used for audio restoration)…"
  command -v brew >/dev/null 2>&1 && brew install sox
fi
command -v sox >/dev/null 2>&1 && echo "  ✓ SoX found"

# 3. Virtual environment + Python packages
echo ""
echo "  • Creating a private environment and installing packages."
echo "    The transcription engine is several GB — this can take a while. ☕"
echo ""
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo ""
echo "============================================"
echo "  ✓ All set!  Double-click  start.command  to run Escriba."
echo "============================================"
read -r -p "  Press Return to close."
