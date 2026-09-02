#!/usr/bin/env bash
# LADLI website — local launcher (macOS / Linux)
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt
echo ""
echo "Starting LADLI website..."
python3 app.py
