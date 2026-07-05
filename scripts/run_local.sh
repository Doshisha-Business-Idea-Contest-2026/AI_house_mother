#!/usr/bin/env bash
# Run the AI House Mother FastAPI app locally with auto-reload.
# Prerequisites:
#   - .venv exists and dependencies are installed (pip install -r requirements.txt)
#   - .env is populated with valid LINE / Gemini credentials
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

if [[ ! -x ".venv/bin/uvicorn" ]]; then
    echo "error: .venv/bin/uvicorn not found. Run 'python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt' first." >&2
    exit 1
fi

PORT="${FASTAPI_PORT:-8084}"
exec .venv/bin/uvicorn src.main:app --reload --host 0.0.0.0 --port "${PORT}"
