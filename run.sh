#!/bin/sh
# STDIO mode startup script for GNS3 MCP Server
set -e

# Change to script directory
cd "$(dirname "$0")"

# Create independent virtual environment (if it doesn't exist)
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..." >&2
    uv venv
    echo "Installing dependencies..." >&2
    echo "Note: Dependency installation may take several minutes. Please wait..." >&2
    uv sync
fi

# Check necessary environment variables
if [[ -z "$GNS3_SERVER_URL" ]]; then
    echo "Warning: GNS3_SERVER_URL environment variable not set (default: http://localhost:3080)" >&2
fi

if [[ -z "$GNS3_USERNAME" ]]; then
    echo "Info: GNS3_USERNAME not set - using anonymous access" >&2
fi

# Start STDIO mode MCP server
exec uv run server.py