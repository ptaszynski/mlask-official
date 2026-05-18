#!/usr/bin/env bash
# ML-Ask Official — convenience launcher for the Streamlit web app.
#
# Prerequisites:
#   pip install 'mlask-official[app]'      # PyPI
#   pip install -e '.[app]'                 # source checkout
#
# Pass any extra `streamlit run` flags through, e.g.
#   bash run_app.sh --server.port 8505
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v streamlit >/dev/null 2>&1; then
    echo "Error: 'streamlit' was not found on PATH."
    echo "Install the app extra first:"
    echo "    pip install 'mlask-official[app]'"
    exit 1
fi

exec streamlit run "$SCRIPT_DIR/streamlit_app.py" --server.headless true "$@"
