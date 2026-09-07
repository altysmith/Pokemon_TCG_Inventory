#!/bin/bash
set -e

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it from https://www.python.org/downloads/macos/ and run this file again."
  read -r -p "Press Return to close."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating the local Python environment..."
  python3 -m venv .venv
fi

if ! .venv/bin/python -c "import PIL, fastapi, uvicorn, httpx" >/dev/null 2>&1; then
  echo "Installing the application dependencies. This can take a few minutes on the first run..."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

echo "Starting Pokemon Card Collection..."
exec .venv/bin/python app.py
