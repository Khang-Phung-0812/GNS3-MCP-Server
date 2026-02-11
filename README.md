# GNS3 MCP Server

MCP server exposing GNS3 automation tools over HTTP JSON-RPC (`/mcp`).

This repo is intended to be portable and publishable. It is not tied to a single local machine.

## What It Does

- Exposes GNS3 project/node/link/simulation operations as MCP tools
- Supports HTTP MCP clients (Codex, Claude Desktop bridges, custom agents)
- Supports direct tool execution and telnet-based console workflows

## Architecture

```text
MCP Client
  -> HTTP MCP Server (FastAPI + Uvicorn, /mcp)
    -> Tool Layer (FastMCP tools in server.py)
      -> GNS3 REST API + Console Ports
```

## Requirements

- Python 3.10+
- `uv` package manager (recommended)
- Running GNS3 server (local or remote)
- Network access from this MCP server host to:
  - `GNS3_SERVER_URL` (default `http://localhost:3080`)
  - Device console ports (for `gns3_exec_cli`, `gns3_push_cli`, `harvest_running_config`)

## Quick Start (Local)

```bash
uv venv
uv sync
export GNS3_SERVER_URL="http://localhost:3080"
uv run uvicorn http_server:app --host 0.0.0.0 --port 9090 --no-access-log
```

Windows PowerShell:

```powershell
uv venv
uv sync
$env:GNS3_SERVER_URL = "http://localhost:3080"
uv run uvicorn http_server:app --host 0.0.0.0 --port 9090 --no-access-log
```

Or use:

```bash
./run.sh
```

## Ubuntu Server + Tailscale Deployment

This is the recommended pattern for remote labs.

### 1) On Ubuntu GNS3 host

Install and run GNS3 server as usual. Confirm it is reachable locally first:

```bash
curl http://127.0.0.1:3080/v2/version
```

### 2) Join Tailscale

On the Ubuntu host:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4
```

If your Ubuntu host (running this MCP server) is `100.86.80.188` and your actual GNS3 API is on `100.95.123.100:3080`:

```text
MCP server: http://100.86.80.188:9090/mcp
GNS3 API:   http://100.95.123.100:3080
```

### 3) Run MCP server with remote GNS3 URL

On the machine running this repo:

```bash
export GNS3_SERVER_URL="http://100.95.123.100:3080"
uv run uvicorn http_server:app --host 0.0.0.0 --port 9090 --no-access-log
```

### 4) Verify MCP endpoint

```bash
curl -s http://127.0.0.1:9090/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}'
```

## Environment Variables

- `GNS3_SERVER_URL`: Base URL for GNS3 API. Default: `http://localhost:3080`

## MCP Methods Supported

- `initialize`
- `tools/list`
- `tools/call`

## Main Tools

- `gns3_list_projects`
- `gns3_create_project`
- `gns3_open_project`
- `gns3_close_project`
- `gns3_add_node`
- `gns3_add_link`
- `gns3_get_topology`
- `gns3_start_simulation`
- `gns3_stop_simulation`
- `gns3_exec_cli`
- `gns3_push_cli`
- `harvest_running_config`
- `bootstrap_devices`

## Example MCP Call

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "gns3_list_projects",
    "arguments": {
      "server_url": "http://100.95.123.100:3080"
    }
  }
}
```

## Security Notes

- Prefer Tailscale/private network over public exposure
- If enabling GNS3 auth, pass `username`/`password` tool arguments
- Restrict console port exposure to trusted network members only

## Repo Hygiene

- `.venv/` and Python caches are git-ignored
- Default URLs are neutral (`localhost`) and override via env vars

## Publishing to GitHub

```bash
git add .
git commit -m "docs: publish portable ubuntu+tailscale setup guide"
git push origin main
```

If push fails from restricted environments, push from your local terminal with normal network access.
