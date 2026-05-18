#!/usr/bin/env bash
# Run ML-Ask Official v0.5 using the shared venv from mlask43-simple-noregex/
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/../mlask43-simple-noregex/.venv"

if [ ! -f "$VENV/bin/streamlit" ]; then
    echo "Error: venv not found at $VENV"
    echo "Run 'pip install -e \".[app]\"' inside the venv first."
    exit 1
fi

PYTHONPATH="$SCRIPT_DIR" "$VENV/bin/streamlit" run \
    "$SCRIPT_DIR/streamlit_app.py" --server.headless true "$@"
