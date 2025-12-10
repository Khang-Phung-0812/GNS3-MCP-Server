#!/bin/sh
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "[INFO] Creating virtual environment..." >&2
    /home/tram/.local/bin/uv venv >&2
    echo "[INFO] Installing dependencies..." >&2
    /home/tram/.local/bin/uv sync >&2
fi

export GNS3_SERVER_URL="http://100.95.123.100:3080"

/home/tram/.local/bin/uv run uvicorn http_server:app --host 0.0.0.0 --port 9090 --no-access-log
