#!/bin/sh
set -e

cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
    echo "[ERROR] 'uv' was not found in PATH. Install uv first: https://docs.astral.sh/uv/" >&2
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "[INFO] Creating virtual environment..." >&2
    uv venv >&2
fi

echo "[INFO] Syncing dependencies..." >&2
uv sync >&2

: "${GNS3_SERVER_URL:=http://localhost:3080}"
export GNS3_SERVER_URL

uv run uvicorn http_server:app --host 0.0.0.0 --port 9090 --no-access-log
