#!/bin/bash
# Escriba — start the app. Double-click to run (after setup.command).
cd "$(dirname "$0")" || exit 1
if [ ! -d ".venv" ]; then
  echo "  Please run setup.command first."
  read -r -p "  Press Return to close."
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python run.py
