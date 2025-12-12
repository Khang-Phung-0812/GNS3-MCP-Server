import os
import json
import logging
import inspect
from types import NoneType
from typing import Any, Dict, Callable, List, Union, get_args, get_origin

import requests
from fastapi import FastAPI, Request
import uvicorn
from fastmcp.tools.tool import ToolResult

# Import your existing async tools from server.py
import server   # this loads gns3_list_projects and others

# Silence noisy logs that might pollute the MCP response
logging.basicConfig(level=logging.CRITICAL)

app = FastAPI()

# Default GNS3 server URL
DEFAULT_GNS3_URL = os.getenv("GNS3_SERVER_URL", "http://100.95.123.100:3080")

# MCP protocol negotiation
SUPPORTED_PROTOCOL_VERSIONS = [
    # Align with currently released mcp-remote clients
    "2024-11-05",
    # Keep latest for future clients
    "2025-02-21",
]
DEFAULT_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]

AUTH_PROPS = {
    "server_url": {
        "type": "string",
        "description": "Base URL of GNS3 server.",
        "default": DEFAULT_GNS3_URL,
    },
    "username": {
        "type": ["string", "null"],
        "description": "Optional authentication username.",
    },
    "password": {
        "type": ["string", "null"],
        "description": "Optional authentication password.",
    },
}

# MCP tool registry (fully enumerated from server.py)
TOOLS: Dict[str, Dict[str, Any]] = {
    # Note: gns3_add_node below is overridden to include compute_id (required by GNS3 API).
    "gns3_list_projects": {
        "func": server.gns3_list_projects,
        "description": "List all GNS3 projects on the server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **AUTH_PROPS,
            },
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_list_projects.",
        },
    },
    "gns3_create_project": {
        "func": server.gns3_create_project,
        "description": "Create a new GNS3 project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the new project.",
                },
                "auto_close": {
                    "type": "boolean",
                    "description": "Auto-close the project when done.",
                    "default": False,
                },
                **AUTH_PROPS,
            },
            "required": ["name"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_create_project.",
        },
    },
    "gns3_open_project": {
        "func": server.gns3_open_project,
        "description": "Open an existing GNS3 project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project to open.",
                },
                **AUTH_PROPS,
            },
            "required": ["project_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_open_project.",
        },
    },
    "gns3_add_node": {
        "func": None,  # filled in after helper definition to include compute_id
        "description": "Add a network device/node to a GNS3 project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID."},
                "node_name": {"type": "string", "description": "Name for the new node."},
                "node_type": {"type": ["string", "null"], "description": "Node type (router, switch, vpcs, etc.). If using a template, this is optional."},
                "template_id": {"type": ["string", "null"], "description": "Template ID to deploy."},
                "template_name": {"type": ["string", "null"], "description": "Template name to deploy (will be looked up)."},
                "x": {"type": ["integer", "null"], "description": "X coordinate on canvas."},
                "y": {"type": ["integer", "null"], "description": "Y coordinate on canvas."},
                "console_type": {"type": ["string", "null"], "description": "Console type to use."},
                "console_auto_start": {
                    "type": "boolean",
                    "description": "Auto-start console.",
                    "default": False,
                },
                "compute_id": {
                    "type": "string",
                    "description": "Compute ID (e.g., local).",
                    "default": "local",
                },
                **AUTH_PROPS,
            },
            "required": ["project_id", "node_name", "compute_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_add_node.",
        },
    },
    "gns3_add_link": {
        "func": server.gns3_add_link,
        "description": "Add a link between two nodes in a GNS3 project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID."},
                "node_a_id": {"type": "string", "description": "ID of the first node."},
                "node_b_id": {"type": "string", "description": "ID of the second node."},
                "node_a_port": {"type": ["string", "null"], "description": "Port on the first node."},
                "node_b_port": {"type": ["string", "null"], "description": "Port on the second node."},
                **AUTH_PROPS,
            },
            "required": ["project_id", "node_a_id", "node_b_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_add_link.",
        },
    },
    "gns3_configure_device": {
        "func": server.gns3_configure_device,
        "description": "Configure settings for a network device.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID."},
                "node_id": {"type": "string", "description": "Node ID to configure."},
                "console_type": {"type": ["string", "null"], "description": "Console type to set."},
                "console_auto_start": {
                    "type": "boolean",
                    "description": "Auto-start console setting.",
                    "default": False,
                },
                "properties": {
                    "type": ["object", "null"],
                    "description": "Additional configuration properties.",
                    "additionalProperties": True,
                },
                **AUTH_PROPS,
            },
            "required": ["project_id", "node_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_configure_device.",
        },
    },
    "gns3_start_simulation": {
        "func": server.gns3_start_simulation,
        "description": "Start all nodes in a network simulation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID."},
                **AUTH_PROPS,
            },
            "required": ["project_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_start_simulation.",
        },
    },
    "gns3_stop_simulation": {
        "func": server.gns3_stop_simulation,
        "description": "Stop all nodes in a network simulation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID."},
                **AUTH_PROPS,
            },
            "required": ["project_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_stop_simulation.",
        },
    },
    "gns3_capture_traffic": {
        "func": server.gns3_capture_traffic,
        "description": "Start capturing network traffic on a link.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID."},
                "link_id": {"type": "string", "description": "Link ID to capture."},
                "capture_file": {"type": "string", "description": "Capture file name."},
                **AUTH_PROPS,
            },
            "required": ["project_id", "link_id", "capture_file"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_capture_traffic.",
        },
    },
    "gns3_get_topology": {
        "func": server.gns3_get_topology,
        "description": "Get the current network topology for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID."},
                **AUTH_PROPS,
            },
            "required": ["project_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_get_topology.",
        },
    },
    "gns3_save_project": {
        "func": server.gns3_save_project,
        "description": "Save a GNS3 project (optionally create a snapshot).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID to save."},
                "snapshot_name": {
                    "type": ["string", "null"],
                    "description": "Optional snapshot name.",
                },
                **AUTH_PROPS,
            },
            "required": ["project_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_save_project.",
        },
    },
    "gns3_export_project": {
        "func": server.gns3_export_project,
        "description": "Export a GNS3 project to a file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID."},
                "export_path": {"type": "string", "description": "Destination path for export."},
                "include_ios_images": {
                    "type": "boolean",
                    "description": "Include IOS images in export.",
                    "default": False,
                },
                "include_node_images": {
                    "type": "boolean",
                    "description": "Include node images in export.",
                    "default": False,
                },
                **AUTH_PROPS,
            },
            "required": ["project_id", "export_path"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from gns3_export_project.",
        },
    },
    "harvest_running_config": {
        "func": server.harvest_running_config,
        "description": "Capture the running configuration from a device using console_harvester.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "Device name to harvest running-config from.",
                },
            },
            "required": ["device"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from harvest_running_config.",
        },
    },
    "bootstrap_devices": {
        "func": server.bootstrap_devices,
        "description": "Write helper/devices.json with provided device/port mappings and fixed console host.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "devices": {
                    "type": "object",
                    "description": "Mapping of device names to console ports.",
                    "additionalProperties": {"type": "integer"},
                },
            },
            "required": ["devices"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Returns JSON data from bootstrap_devices.",
        },
    },
}


def gns3_add_node_with_compute(
    project_id: str,
    node_name: str,
    node_type: str | None = None,
    template_id: str | None = None,
    template_name: str | None = None,
    compute_id: str = "local",
    x: int | None = None,
    y: int | None = None,
    console_type: str | None = None,
    console_auto_start: bool = False,
    server_url: str = DEFAULT_GNS3_URL,
    username: str | None = None,
    password: str | None = None,
) -> Dict[str, Any]:
    """
    Wrapper to add a node and include compute_id (required by GNS3 API).
    Supports template_id/template_name for template-based deployments.
    """
    auth = (username, password) if username else None

    # Resolve template_id by name if provided
    if not template_id and template_name:
        t_resp = requests.get(
            f"{server_url}/v2/templates", auth=auth, timeout=30)
        if not t_resp.ok:
            raise Exception(
                f"GNS3 API error: {t_resp.status_code} - {t_resp.text}")
        templates = t_resp.json() or []
        for t in templates:
            if t.get("name") == template_name:
                template_id = t.get("template_id")
                break
        if not template_id:
            raise Exception(
                f"Template '{template_name}' not found on GNS3 server.")

    # If template_id resolved, deploy from template
    if template_id:
        url = f"{server_url}/v2/projects/{project_id}/templates/{template_id}"
        payload = {
            "name": node_name,
            "compute_id": compute_id,
            "x": x,
            "y": y,
            # Some template deployments reject extra properties; keep minimal payload.
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        resp = requests.post(url, json=payload, auth=auth, timeout=30)
        if not resp.ok:
            raise Exception(
                f"GNS3 API error: {resp.status_code} - {resp.text}")
        return resp.json()

    # Otherwise fall back to raw node creation (must have node_type)
    if not node_type:
        raise Exception(
            "node_type is required when not deploying from a template.")

    url = f"{server_url}/v2/projects/{project_id}/nodes"
    payload = {
        "name": node_name,
        "node_type": node_type,
        "compute_id": compute_id,
        "x": x,
        "y": y,
        "console_type": console_type,
        "console_auto_start": console_auto_start,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    resp = requests.post(url, json=payload, auth=auth, timeout=30)
    if not resp.ok:
        raise Exception(f"GNS3 API error: {resp.status_code} - {resp.text}")
    return resp.json()


# Override the add_node func to the wrapper that sends compute_id.
TOOLS["gns3_add_node"]["func"] = gns3_add_node_with_compute


def make_tool_descriptor(name: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Return MCP-compliant tool descriptor."""
    return {
        "name": name,
        "description": meta["description"],
        "inputSchema": meta["inputSchema"],
        "outputSchema": meta["outputSchema"],
    }


def _annotation_to_json_types(annotation: Any) -> Any:
    """
    Convert Python type annotations into a basic JSON schema type or list of types.
    Falls back to "string" when unknown to keep schemas permissive.
    """
    if annotation is inspect._empty:
        return "string"

    origin = get_origin(annotation)
    args = get_args(annotation)

    if annotation is NoneType:
        return "null"

    if origin is Union:
        mapped = []
        for arg in args:
            t = _annotation_to_json_types(arg)
            if isinstance(t, list):
                mapped.extend(t)
            else:
                mapped.append(t)
        return list(dict.fromkeys(mapped)) or "string"

    if origin in (list, List):
        return "array"
    if origin in (dict, Dict):
        return "object"
    if origin is None:
        mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array",
        }
        return mapping.get(annotation, "string")

    return "string"


def build_schema_from_signature(func: Callable) -> Dict[str, Any]:
    """Generate a permissive JSON schema from a function signature."""
    target = getattr(func, "fn", func)
    sig = inspect.signature(target)
    properties: Dict[str, Any] = {}
    required = []

    for name, param in sig.parameters.items():
        json_type = _annotation_to_json_types(param.annotation)
        prop: Dict[str, Any] = {
            "type": json_type,
            "description": f"Parameter {name}.",
        }
        if param.default is not inspect._empty:
            prop["default"] = param.default
        else:
            required.append(name)
        properties[name] = prop

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def discover_server_tools(existing_tools: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Auto-discover any attribute named gns3_* in server.py and add it to the registry if it is missing.
    We avoid predicate=callable because @mcp.tool wrappers may not expose __call__.
    """
    discovered: Dict[str, Dict[str, Any]] = {}
    for name in dir(server):
        if not name.startswith("gns3_"):
            continue
        if name in existing_tools:
            continue

        func_obj = getattr(server, name)
        description = (inspect.getdoc(func_obj)
                       or f"{name} tool from server.py").strip().splitlines()[0]

        discovered[name] = {
            "func": func_obj,
            "description": description,
            "inputSchema": build_schema_from_signature(func_obj),
            "outputSchema": {
                "type": "object",
                "description": f"Returns JSON data from {name}.",
            },
        }
    return discovered


TOOLS.update(discover_server_tools(TOOLS))


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    Minimal but fully MCP-compliant HTTP JSON-RPC endpoint.

    Supports:
      • initialize
      • tools/list
      • tools/call
    """
    try:
        body = await request.json()
    except Exception:
        # Bad JSON → MCP error
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Invalid JSON received.",
            },
        }

    jsonrpc = body.get("jsonrpc", "2.0")
    method = body.get("method")
    req_id = body.get("id")

    # ------------------------ 1) MCP initialize ------------------------
    if method == "initialize":
        requested_protocol = (
            (body.get("params") or {}).get("protocolVersion")
            if isinstance(body, dict)
            else None
        )
        if requested_protocol:
            requested_protocol = str(requested_protocol)

        protocol_version = (
            requested_protocol
            if requested_protocol in SUPPORTED_PROTOCOL_VERSIONS
            else DEFAULT_PROTOCOL_VERSION
        )

        return {
            "jsonrpc": jsonrpc,
            "id": req_id,
            "result": {
                "protocolVersion": protocol_version,
                "serverInfo": {
                    "name": "gns3-mcp-http",
                    "version": "0.2.0",
                },
                "capabilities": {
                    "tools": {},
                },
            },
        }

    # ------------------------ 2) tools/list ------------------------
    if method == "tools/list":
        tools_list = [
            make_tool_descriptor(name, meta)
            for name, meta in TOOLS.items()
        ]
        return {
            "jsonrpc": jsonrpc,
            "id": req_id,
            "result": {
                "tools": tools_list,
                "nextCursor": None,
            },
        }

    # ------------------------ 3) tools/call ------------------------
    if method == "tools/call":
        params = body.get("params", {}) or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {}) or {}

        if tool_name not in TOOLS:
            return {
                "jsonrpc": jsonrpc,
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}",
                },
            }

        func_obj: Callable = TOOLS[tool_name]["func"]

        # FastMCP @mcp.tool decorators wrap functions in FunctionTool objects.
        # Use the underlying .fn when present so we can actually call the coroutine.
        if hasattr(func_obj, "fn"):
            callable_func = func_obj.fn  # unwrap FunctionTool
        elif hasattr(func_obj, "run"):
            # Some tool wrappers expose a run(arguments) helper; adapt to our call style.
            callable_func = lambda **kwargs: func_obj.run(kwargs)
        else:
            callable_func = func_obj

        # Fill defaults only when the target supports them
        target_sig = inspect.signature(callable_func)
        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in target_sig.parameters.values()
        )
        if "server_url" in target_sig.parameters and not arguments.get("server_url"):
            arguments["server_url"] = DEFAULT_GNS3_URL
        if not accepts_kwargs:
            arguments = {
                k: v for k, v in arguments.items() if k in target_sig.parameters
            }

        try:
            # Call your async function from server.py
            result = callable_func(**arguments)
            result_payload = await result if inspect.isawaitable(result) else result

            # Normalize payload for MCP response
            structured_content = None
            text_payload: Any = result_payload

            if isinstance(result_payload, ToolResult):
                structured_content = result_payload.structured_content
                text_payload = structured_content if structured_content is not None else result_payload.content
            else:
                structured_content = result_payload

            # Ensure JSON-serializable structured content
            try:
                structured_json = json.loads(
                    json.dumps(structured_content, default=str)
                ) if structured_content is not None else None
            except Exception:
                structured_json = {"value": str(structured_content)}

            # Build MCP success response with valid content type
            return {
                "jsonrpc": jsonrpc,
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(text_payload, default=str),
                        }
                    ],
                    "structuredContent": structured_json,
                    "isError": False,
                },
            }

        except Exception as e:
            logging.exception("Tool execution failed:")
            return {
                "jsonrpc": jsonrpc,
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Tool '{tool_name}' failed: {e}",
                        }
                    ],
                    "isError": True,
                },
            }

    # ------------------------ Unknown Method ------------------------
    return {
        "jsonrpc": jsonrpc,
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Unknown method '{method}'",
        },
    }


if __name__ == "__main__":
    uvicorn.run(
        "http_server:app",
        host="0.0.0.0",
        port=9090,
        reload=False,
        access_log=False,
    )
