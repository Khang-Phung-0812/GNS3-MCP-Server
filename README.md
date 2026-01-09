# GNS3 MCP Server

[![MCP Protocol](https://img.shields.io/badge/MCP-Protocol-blue.svg)](https://modelcontextprotocol.io/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.x-green.svg)](https://github.com/anselmholden/fastmcp)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-teal.svg)](https://fastapi.tiangolo.com/)
[![Uvicorn](https://img.shields.io/badge/Uvicorn-0.30+-purple.svg)](https://www.uvicorn.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow.svg)](https://python.org)
[![GNS3](https://img.shields.io/badge/GNS3-Compatible-orange.svg)](https://gns3.com/)

> **AI-ready, MCP-based control plane for GNS3 automation**  
> Deterministic tools, clean schemas, and a production-style HTTP MCP surface for network labs.

---

## What This Is ✅

- An MCP-compliant execution layer for GNS3, built with FastMCP
- A clean separation between reasoning (agent) and execution (this server)
- A schema-defined tool surface over direct GNS3 REST API calls
- A control plane for on-prem or remote network labs

## What This Is Not ❌

- No natural language interpretation inside the MCP server
- No topology intelligence or AI reasoning
- No automated configuration generation beyond explicit tool calls
- No analytics or ML logic

---

## Architecture Overview 🧭

```
MCP Client
   |
   v
HTTP MCP Server (FastAPI + Uvicorn, /mcp, JSON-RPC)
   |
   v
Tool Layer (FastMCP tools in server.py)
   |
   v
GNS3 Server (REST API + console ports)
```

Why HTTP MCP matters:
- Standardized JSON-RPC endpoint for tool discovery and invocation
- Easy to front with proxies, gateways, or internal service meshes
- Clear separation of transport (http_server.py) and tool logic (server.py)

---

## Why MCP for GNS3? 💡

- **Not the GUI**: deterministic automation beats point-and-click for repeatable labs
- **Not raw REST**: MCP adds discoverable tools and structured schemas
- **Agent-friendly**: safe, explicit parameters with no hidden execution
- **Automation-ready**: works with Codex, Claude, Gemini, or custom orchestrators

---

## Implemented MCP Tools 🧰

All tools below exist in `server.py` and are exposed through `http_server.py`.

| Category | Tool | Purpose |
|---|---|---|
| Project | `gns3_list_projects` | List projects with status and stats |
| Project | `gns3_create_project` | Create a project |
| Project | `gns3_open_project` | Open a project |
| Project | `gns3_close_project` | Close a project |
| Project | `gns3_save_project` | Save project (optional snapshot) |
| Project | `gns3_update_project` | Update project name/auto_close |
| Project | `gns3_get_project_settings` | Read project settings |
| Nodes | `gns3_add_node` | Add a node (supports compute_id, templates) |
| Nodes | `gns3_get_node` | Get node details |
| Nodes | `gns3_configure_device` | Update node properties |
| Links | `gns3_add_link` | Create a link between nodes |
| Links | `gns3_delete_link` | Delete a link |
| Simulation | `gns3_start_simulation` | Start all nodes |
| Simulation | `gns3_stop_simulation` | Stop all nodes |
| Topology | `gns3_get_topology` | Summarize nodes and links |
| Traffic | `gns3_capture_traffic` | Start capture on a link |
| Console | `gns3_push_cli` | Send CLI commands via telnet |
| Console | `gns3_exec_cli` | Execute commands and return output |
| Console | `harvest_running_config` | Capture running-config via telnet |
| Console | `bootstrap_devices` | Create `helper/devices.json` mappings |
| Export | `gns3_export_project` | Prepare export parameters (UI completes export) |

---

## Installation & Running Modes 🚀

### 1) Local tool layer (FastMCP)
Runs the tool layer directly:

```bash
python server.py
```

### 2) HTTP MCP server (FastAPI + Uvicorn)

```bash
uvicorn http_server:app --host 0.0.0.0 --port 9090 --no-access-log
```

The `/mcp` endpoint supports MCP JSON-RPC:
- `initialize`
- `tools/list`
- `tools/call`

### 3) `run.sh` bootstrap (uv-based)
For environments that use `uv`:

```bash
./run.sh
```

---

## Environment Variables ⚙️

| Variable | Purpose | Default |
|---|---|---|
| `GNS3_SERVER_URL` | Base URL for the GNS3 server | `http://100.95.123.100:3080` |

---

## Example MCP Workflows 🔧

### Example 1: Project lifecycle
1. Call `gns3_create_project` with `name`
2. Call `gns3_open_project` with `project_id`
3. Call `gns3_save_project` (optional snapshot)
4. Call `gns3_close_project`

### Example 2: Build a minimal topology
1. `gns3_add_node` (router, switch, etc.)
2. `gns3_add_link` between nodes
3. `gns3_start_simulation`
4. `gns3_get_topology` to verify

### Example 3: Console workflow
1. `gns3_exec_cli` to run show commands
2. `gns3_push_cli` to apply config changes
3. `harvest_running_config` to pull running-config

### MCP JSON-RPC call (tools/call)

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

---

## Design & Security Notes 🔒

- Schema-driven tools with explicit parameters
- Deterministic tool execution; no hidden behavior
- On-prem friendly: all calls route to your GNS3 server
- Console access uses telnet; ensure console ports are reachable

---

## Limitations & Scope 🧱

- No natural language parsing or reasoning inside the MCP server
- No topology inference or optimization
- `gns3_export_project` only prepares parameters; GNS3 UI performs export
- Console tools require working telnet console access
- `harvest_running_config` depends on `helper/devices.json` mappings

---

## Future Roadmap (Planned) 🗺️

> These are future ideas, not current features.

- AI-assisted topology suggestions
- Config generation workflows
- Validation and drift checks
- Lab analytics and reporting

---