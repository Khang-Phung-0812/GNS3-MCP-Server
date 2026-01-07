#!/usr/bin/env python3
"""
GNS3 MCP Server - FastMCP implementation for GNS3 network simulation integration.

This MCP server provides tools for managing GNS3 network topologies,
project management, and simulation control through direct HTTP API calls.
"""
from pydantic import BaseModel, Field
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
import httpx
from typing import Any, Dict, List, Optional
import json
import asyncio
import sys
import logging
import time
from urllib.parse import urlparse
from helper.console_harvester import capture_running_config
import os

# Silence all logging that might print to STDOUT
logging.getLogger().setLevel(logging.CRITICAL)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP("GNS3 Network Simulator")

# Configuration models
DEVICES_FILE = os.path.join(os.path.dirname(__file__), "helper", "devices.json")

LOCAL_CONSOLE_HOSTS = {"", "0.0.0.0", "127.0.0.1", "localhost"}


def _resolve_console_host(
    console_host: Optional[str],
    node_console_host: Optional[str],
    server_url: str,
) -> str:
    """
    Resolve console host, preferring explicit overrides and normalizing local binds.
    """
    host = console_host or node_console_host or ""
    if host in LOCAL_CONSOLE_HOSTS:
        parsed = urlparse(server_url)
        return parsed.hostname or "127.0.0.1"
    return host


class GNS3Config(BaseModel):
    """Configuration for GNS3 server connection."""
    server_url: str = Field(default="http://100.95.123.100:3080",
                            description="GNS3 server URL")
    username: Optional[str] = Field(
        default=None, description="Username for authentication")
    password: Optional[str] = Field(
        default=None, description="Password for authentication")
    verify_ssl: bool = Field(
        default=True, description="Verify SSL certificates")


class GNS3APIClient:
    """HTTP client for GNS3 REST API."""

    def __init__(self, config: GNS3Config):
        self.config = config
        self.base_url = config.server_url.rstrip('/')
        self.auth = None
        if config.username and config.password:
            self.auth = (config.username, config.password)

    async def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to GNS3 API."""
        url = f"{self.base_url}/v2{endpoint}"
        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(verify=self.config.verify_ssl, timeout=30.0) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, auth=self.auth)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data, headers=headers, auth=self.auth)
                elif method.upper() == "PUT":
                    response = await client.put(url, json=data, headers=headers, auth=self.auth)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers, auth=self.auth)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json()

        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise Exception(f"Failed to connect to GNS3 server: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            raise Exception(
                f"GNS3 API error: {e.response.status_code} - {e.response.text}")

    async def get_server_info(self) -> Dict[str, Any]:
        """Get GNS3 server information."""
        return await self._request("GET", "/version")

    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects."""
        return await self._request("GET", "/projects")

    async def create_project(self, name: str, auto_close: bool = False) -> Dict[str, Any]:
        """Create a new project."""
        data = {
            "name": name,
            "auto_close": auto_close
        }
        return await self._request("POST", "/projects", data)

    async def get_project(self, project_id: str) -> Dict[str, Any]:
        """Get project details."""
        return await self._request("GET", f"/projects/{project_id}")

    async def open_project(self, project_id: str) -> Dict[str, Any]:
        """Open a project."""
        return await self._request("POST", f"/projects/{project_id}/open")

    async def close_project(self, project_id: str) -> Dict[str, Any]:
        """Close a project."""
        return await self._request("POST", f"/projects/{project_id}/close")

    async def get_project_nodes(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all nodes in a project."""
        return await self._request("GET", f"/projects/{project_id}/nodes")

    async def get_project_links(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all links in a project."""
        return await self._request("GET", f"/projects/{project_id}/links")

    async def create_node(self, project_id: str, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new node."""
        return await self._request("POST", f"/projects/{project_id}/nodes", node_data)

    async def get_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """Get node details."""
        return await self._request("GET", f"/projects/{project_id}/nodes/{node_id}")

    async def update_node(self, project_id: str, node_id: str, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update node."""
        return await self._request("PUT", f"/projects/{project_id}/nodes/{node_id}", node_data)

    async def start_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """Start a node."""
        return await self._request("POST", f"/projects/{project_id}/nodes/{node_id}/start")

    async def stop_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """Stop a node."""
        return await self._request("POST", f"/projects/{project_id}/nodes/{node_id}/stop")

    async def create_link(self, project_id: str, link_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new link."""
        return await self._request("POST", f"/projects/{project_id}/links", link_data)

    async def start_capture(self, project_id: str, link_id: str, capture_file_name: str) -> Dict[str, Any]:
        """Start packet capture on a link."""
        data = {"capture_file_name": capture_file_name}
        return await self._request("POST", f"/projects/{project_id}/links/{link_id}/start_capture", data)

    async def delete_link(self, project_id: str, link_id: str) -> Dict[str, Any]:
        """Delete a link."""
        return await self._request("DELETE", f"/projects/{project_id}/links/{link_id}")

    async def create_snapshot(self, project_id: str, name: str) -> Dict[str, Any]:
        """Create a project snapshot."""
        data = {"name": name}
        return await self._request("POST", f"/projects/{project_id}/snapshots", data)

    async def update_project(self, project_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update project properties."""
        return await self._request("PUT", f"/projects/{project_id}", data)

# Tool: List all GNS3 projects


@mcp.tool
async def gns3_list_projects(
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """List all projects on the GNS3 server.

    Args:
        server_url: GNS3 server URL (default: http://localhost:3080)
        username: Optional username for authentication
        password: Optional password for authentication

    Returns:
        Dictionary containing project list with status
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Get server info
        server_info = await client.get_server_info()

        # Get projects
        projects = await client.get_projects()

        # Format projects summary
        projects_summary = []
        for project in projects:
            projects_summary.append({
                "Project Name": project.get("name", "Unnamed"),
                "Project ID": project.get("project_id", ""),
                "Total Nodes": project.get("stats", {}).get("nodes", 0),
                "Total Links": project.get("stats", {}).get("links", 0),
                "Status": project.get("status", "unknown")
            })

        result_payload = {
            "status": "success",
            "server_info": {
                "version": server_info.get("version", "unknown"),
                "user": server_info.get("user", "anonymous")
            },
            "projects": projects_summary,
            "total_projects": len(projects_summary)
        }

        # Return structured content to satisfy MCP tool expectations
        return ToolResult(structured_content=result_payload)
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        return {
            "status": "error",
            "error": str(e),
            "projects": [],
            "total_projects": 0
        }

# Tool: Create a new GNS3 project


@mcp.tool
async def gns3_create_project(
    name: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None,
    auto_close: bool = False
) -> Dict[str, Any]:
    """Create a new GNS3 project.

    Args:
        name: Name for the new project
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication
        auto_close: Auto-close the project when done

    Returns:
        Dictionary containing project creation result
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Create project
        project = await client.create_project(name, auto_close)

        return {
            "status": "success",
            "project": {
                "project_id": project.get("project_id"),
                "name": project.get("name"),
                "status": project.get("status"),
                "auto_close": project.get("auto_close", False)
            }
        }
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        return {
            "status": "error",
            "error": str(e),
            "project": None
        }

# Tool: Open an existing project


@mcp.tool
async def gns3_open_project(
    project_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """Open an existing GNS3 project.

    Args:
        project_id: ID of the project to open
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication

    Returns:
        Dictionary containing project opening result
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Get project details
        project = await client.get_project(project_id)

        # Open project
        opened_project = await client.open_project(project_id)

        return {
            "status": "success",
            "project": {
                "project_id": opened_project.get("project_id"),
                "name": opened_project.get("name"),
                "status": opened_project.get("status"),
                "auto_close": opened_project.get("auto_close", False),
                "stats": opened_project.get("stats", {})
            }
        }
    except Exception as e:
        logger.error(f"Failed to open project: {e}")
        return {
            "status": "error",
            "error": str(e),
            "project": None
        }

# Tool: Close an open project


@mcp.tool
async def gns3_close_project(
    project_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """Close an open GNS3 project."""
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Close project
        closed_project = await client.close_project(project_id)

        return {
            "status": "success",
            "project": {
                "project_id": closed_project.get("project_id"),
                "name": closed_project.get("name"),
                "status": closed_project.get("status", "closed"),
                "auto_close": closed_project.get("auto_close", False),
                "stats": closed_project.get("stats", {})
            }
        }
    except Exception as e:
        logger.error(f"Failed to close project: {e}")
        return {
            "status": "error",
            "error": str(e),
            "project": None
        }

# Tool: Add a network node/device


@mcp.tool
async def gns3_add_node(
    project_id: str,
    node_name: str,
    node_type: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    console_type: Optional[str] = None,
    console_auto_start: bool = False
) -> Dict[str, Any]:
    """Add a network device/node to a GNS3 project.

    Args:
        project_id: ID of the project to add node to
        node_name: Name for the new node
        node_type: Type of node (e.g., 'router', 'ethernet_switch', 'vpcs')
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication
        x: X coordinate on the canvas (optional)
        y: Y coordinate on the canvas (optional)
        console_type: Console type (optional)
        console_auto_start: Auto-start console (optional)

    Returns:
        Dictionary containing node addition result
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Prepare node data
        node_data = {
            "name": node_name,
            "node_type": node_type
        }

        if x is not None:
            node_data["x"] = x
        if y is not None:
            node_data["y"] = y
        if console_type is not None:
            node_data["console_type"] = console_type
        if console_auto_start:
            node_data["console_auto_start"] = console_auto_start

        # Create node
        node = await client.create_node(project_id, node_data)

        return {
            "status": "success",
            "node": {
                "node_id": node.get("node_id"),
                "name": node.get("name"),
                "node_type": node.get("node_type"),
                "status": node.get("status"),
                "x": node.get("x"),
                "y": node.get("y"),
                "console": node.get("console")
            }
        }
    except Exception as e:
        logger.error(f"Failed to add node: {e}")
        return {
            "status": "error",
            "error": str(e),
            "node": None
        }

# Tool: Add a link between two nodes


@mcp.tool
async def gns3_add_link(
    project_id: str,
    node_a_id: str,
    node_b_id: str,
    node_a_port: Optional[str] = None,
    node_b_port: Optional[str] = None,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """Add a link between two nodes in a GNS3 project.

    Args:
        project_id: ID of the project
        node_a_id: ID of the first node
        node_b_id: ID of the second node
        node_a_port: Port on the first node (optional)
        node_b_port: Port on the second node (optional)
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication

    Returns:
        Dictionary containing link addition result
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        def parse_port(port: Optional[str]) -> Dict[str, int]:
            """
            Convert interface strings into adapter/port numbers.
            Rules:
            - Gigabit/Fast (Gi/Fa...) on IOSv/IOSvL3 (qemu): adapter = (first number * 4) + second number, port = 0.
              e.g., Gi0/1 -> adapter 1, Gi1/0 -> adapter 4, Gi3/2 -> adapter 14.
            - EthernetX/Y on IOU: adapter = X, port = Y.
            - Numeric "X/Y": adapter = X, port = Y.
            - Single numeric "N": adapter = 0, port = N.
            """
            if port is None:
                raise ValueError("port is required")
            if isinstance(port, (list, tuple)) and len(port) == 2:
                return {"adapter_number": int(port[0]), "port_number": int(port[1])}
            if not isinstance(port, str):
                raise ValueError(f"Unable to parse port '{port}'")

            p = port.strip()
            # Identify prefix
            prefix = ''.join(ch for ch in p if ch.isalpha())
            # Strip leading letters for numeric split
            while p and not p[0].isdigit():
                p = p[1:]
            # Split numbers
            if "/" in p:
                a_str, b_str = p.split("/", 1)
                a, b = int(a_str), int(b_str)
                if prefix.lower().startswith(("gi", "fa")):
                    adapter_idx = a * 4 + b
                    return {"adapter_number": adapter_idx, "port_number": 0}
                # IOU Ethernet and generic
                return {"adapter_number": a, "port_number": b}
            if p.isdigit():
                return {"adapter_number": 0, "port_number": int(p)}

            raise ValueError(f"Unable to parse port '{port}'")

        # Prepare link data with adapter/port numbers when possible
        nodes = []
        for nid, p in ((node_a_id, node_a_port), (node_b_id, node_b_port)):
            entry: Dict[str, Any] = {"node_id": nid}
            parsed = parse_port(p)
            entry.update(parsed)
            nodes.append(entry)

        link_data = {"nodes": nodes}

        # Create link
        link = await client.create_link(project_id, link_data)

        return {
            "status": "success",
            "link": {
                "link_id": link.get("link_id"),
                "link_type": link.get("link_type", "ethernet"),
                "nodes": link.get("nodes", []),
                "capturing": link.get("capturing", False)
            }
        }
    except Exception as e:
        logger.error(f"Failed to add link: {e}")
        return {
            "status": "error",
            "error": str(e),
            "link": None
        }

# Tool: Configure device settings


@mcp.tool
async def gns3_configure_device(
    project_id: str,
    node_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None,
    console_type: Optional[str] = None,
    console_auto_start: bool = False,
    properties: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Configure settings for a network device.

    Args:
        project_id: ID of the project
        node_id: ID of the node to configure
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication
        console_type: Console type to configure (optional)
        console_auto_start: Auto-start console setting (optional)
        properties: Additional configuration properties (optional)

    Returns:
        Dictionary containing configuration result
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Prepare configuration parameters
        config_params = {}
        if console_type is not None:
            config_params["console_type"] = console_type
        if console_auto_start:
            config_params["console_auto_start"] = console_auto_start
        if properties is not None:
            config_params.update(properties)

        # Update node configuration
        updated_node = await client.update_node(project_id, node_id, config_params)

        return {
            "status": "success",
            "node": {
                "node_id": updated_node.get("node_id"),
                "name": updated_node.get("name"),
                "node_type": updated_node.get("node_type"),
                "status": updated_node.get("status"),
                "config_updated": list(config_params.keys())
            }
        }
    except Exception as e:
        logger.error(f"Failed to configure device: {e}")
        return {
            "status": "error",
            "error": str(e),
            "node": None
        }

# Tool: Start network simulation


@mcp.tool
async def gns3_start_simulation(
    project_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """Start all nodes in a network simulation.

    Args:
        project_id: ID of the project to start
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication

    Returns:
        Dictionary containing simulation start result
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Get all nodes
        nodes = await client.get_project_nodes(project_id)

        started_nodes = []
        failed_nodes = []

        # Start each node
        for node in nodes:
            try:
                await client.start_node(project_id, node["node_id"])
                started_nodes.append({
                    "node_id": node["node_id"],
                    "name": node["name"],
                    "status": "started"
                })
            except Exception as e:
                failed_nodes.append({
                    "node_id": node["node_id"],
                    "name": node["name"],
                    "error": str(e)
                })

        return {
            "status": "success",
            "project_id": project_id,
            "started_nodes": started_nodes,
            "failed_nodes": failed_nodes,
            "total_nodes": len(nodes),
            "successful_starts": len(started_nodes)
        }
    except Exception as e:
        logger.error(f"Failed to start simulation: {e}")
        return {
            "status": "error",
            "error": str(e),
            "project_id": project_id
        }

# Tool: Stop network simulation


@mcp.tool
async def gns3_stop_simulation(
    project_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """Stop all nodes in a network simulation.

    Args:
        project_id: ID of the project to stop
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication

    Returns:
        Dictionary containing simulation stop result
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Get all nodes
        nodes = await client.get_project_nodes(project_id)

        stopped_nodes = []
        failed_nodes = []

        # Stop each node
        for node in nodes:
            try:
                await client.stop_node(project_id, node["node_id"])
                stopped_nodes.append({
                    "node_id": node["node_id"],
                    "name": node["name"],
                    "status": "stopped"
                })
            except Exception as e:
                failed_nodes.append({
                    "node_id": node["node_id"],
                    "name": node["name"],
                    "error": str(e)
                })

        return {
            "status": "success",
            "project_id": project_id,
            "stopped_nodes": stopped_nodes,
            "failed_nodes": failed_nodes,
            "total_nodes": len(nodes),
            "successful_stops": len(stopped_nodes)
        }
    except Exception as e:
        logger.error(f"Failed to stop simulation: {e}")
        return {
            "status": "error",
            "error": str(e),
            "project_id": project_id
        }

# Tool: Capture network traffic on links


@mcp.tool
async def gns3_capture_traffic(
    project_id: str,
    link_id: str,
    capture_file: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """Start capturing network traffic on a link.

    Args:
        project_id: ID of the project
        link_id: ID of the link to capture on
        capture_file: Name for the capture file
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication

    Returns:
        Dictionary containing capture initiation result
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Start capture
        result = await client.start_capture(project_id, link_id, capture_file)

        return {
            "status": "success",
            "link_id": link_id,
            "capture_started": True,
            "capture_file": capture_file,
            "capture_result": result
        }
    except Exception as e:
        logger.error(f"Failed to start traffic capture: {e}")
        return {
            "status": "error",
            "error": str(e),
            "link_id": link_id
        }

# Tool: Push CLI commands to a node console (telnet)


@mcp.tool
async def gns3_push_cli(
    project_id: str,
    node_id: str,
    commands: List[str],
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None,
    enable_password: Optional[str] = None,
    console_host: Optional[str] = None,
    console_port: Optional[int] = None,
    delay_seconds: float = 0.2,
    timeout_seconds: float = 8.0
) -> Dict[str, Any]:
    """Push CLI lines to a node via its telnet console.

    Args:
        project_id: ID of the project
        node_id: ID of the node to configure
        commands: Ordered list of CLI lines to send (no prompts required)
        server_url: GNS3 server URL (used to resolve console host if not provided)
        username/password: Optional HTTP auth for GNS3 API (not for console)
        enable_password: Optional password to send after an "enable" command
        console_host/console_port: Override console endpoint; if omitted, fetched from node details
        delay_seconds: Sleep between commands to allow device to process
        timeout_seconds: Socket timeout for the telnet session
    """
    try:
        try:
            import telnetlib  # type: ignore
        except ModuleNotFoundError:
            raise ImportError(
                "telnetlib is unavailable in this Python version. Install a telnet client library (e.g., telnetlib3) or run with Python 3.12 or below."
            )

        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Resolve console endpoint from node details when not provided
        node = await client.get_node(project_id, node_id)
        host = _resolve_console_host(
            console_host, node.get("console_host"), server_url)
        port = console_port or node.get("console")
        if port is None:
            raise Exception("Console port not available for this node.")

        send_lines = list(commands or [])

        def push_sync() -> Dict[str, Any]:
            tn = telnetlib.Telnet(host, int(port), timeout_seconds)
            # Nudge the prompt
            tn.write(b"\n")
            time.sleep(delay_seconds)
            if enable_password:
                tn.write(b"enable\n")
                time.sleep(delay_seconds)
                tn.write((enable_password + "\n").encode())
                time.sleep(delay_seconds)
            for line in send_lines:
                tn.write((line + "\n").encode())
                time.sleep(delay_seconds)
            tn.write(b"\n")
            tn.close()
            return {"sent": send_lines}

        result = await asyncio.to_thread(push_sync)
        return {
            "status": "success",
            "console_host": host,
            "console_port": port,
            "sent_commands": result.get("sent", [])
        }
    except Exception as e:
        logger.error(f"Failed to push CLI: {e}")
        return {
            "status": "error",
            "error": str(e),
            "node_id": node_id
        }


@mcp.tool
async def gns3_exec_cli(
    project_id: str,
    node_id: str,
    commands: List[str],
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None,
    enable_password: Optional[str] = None,
    console_host: Optional[str] = None,
    console_port: Optional[int] = None,
    delay_seconds: float = 0.3,
    timeout_seconds: float = 10.0,
) -> Dict[str, Any]:
    """
    Execute CLI commands on a node and capture output via telnet.

    Args mirror gns3_push_cli but return captured output lines.
    """
    try:
        try:
            import telnetlib  # type: ignore
        except ModuleNotFoundError:
            raise ImportError(
                "telnetlib is unavailable in this Python version. Install a telnet client library (e.g., telnetlib3) or run with Python 3.12 or below."
            )

        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Resolve console endpoint
        node = await client.get_node(project_id, node_id)
        host = _resolve_console_host(
            console_host, node.get("console_host"), server_url)
        port = console_port or node.get("console")
        if port is None:
            raise Exception("Console port not available for this node.")

        send_lines = list(commands or [])

        def exec_sync() -> Dict[str, Any]:
            tn = telnetlib.Telnet(host, int(port), timeout_seconds)
            buf: List[str] = []
            tn.write(b"\n")
            time.sleep(delay_seconds)
            if enable_password:
                tn.write(b"enable\n")
                time.sleep(delay_seconds)
                tn.write((enable_password + "\n").encode())
                time.sleep(delay_seconds)
            for line in send_lines:
                tn.write((line + "\n").encode())
                time.sleep(delay_seconds)
            time.sleep(delay_seconds)
            try:
                # Read whatever is available without blocking too long
                buf_bytes = tn.read_very_eager()
                if buf_bytes:
                    buf.append(buf_bytes.decode(errors="ignore"))
            except Exception:
                pass
            tn.write(b"\n")
            tn.close()
            return {"sent": send_lines, "output": "".join(buf)}

        result = await asyncio.to_thread(exec_sync)
        return {
            "status": "success",
            "console_host": host,
            "console_port": port,
            "sent_commands": result.get("sent", []),
            "output": result.get("output", "")
        }
    except Exception as e:
        logger.error(f"Failed to exec CLI: {e}")
        return {
            "status": "error",
            "error": str(e),
            "node_id": node_id
        }

# Tool: Harvest running config via console harvester


@mcp.tool
async def harvest_running_config(
    device: str,
    server_url: Optional[str] = None,
) -> Dict[str, str]:
    """Capture the running configuration from a device using console_harvester."""
    try:
        if not isinstance(device, str) or not device.strip():
            return {
                "status": "error",
                "device": "" if device is None else str(device),
                "error": "device must be a non-empty string"
            }

        target_device = device.strip()
        config = await asyncio.to_thread(
            capture_running_config, target_device, server_url)

        return {
            "status": "success",
            "device": target_device,
            "config": config
        }
    except Exception as e:
        logger.error(f"Failed to harvest running config: {e}")
        return {
            "status": "error",
            "device": "" if device is None else str(device),
            "error": str(e)
        }


@mcp.tool
async def bootstrap_devices(devices: Dict[str, int]) -> Dict[str, Any]:
    """
    Write helper/devices.json with provided device/port mappings and fixed console host.
    """
    try:
        if not isinstance(devices, dict):
            return {
                "status": "error",
                "error": "devices must be an object mapping device names to integer ports",
            }

        normalized: Dict[str, Dict[str, Any]] = {}
        for name, port in devices.items():
            if not isinstance(name, str) or not name.strip():
                return {
                    "status": "error",
                    "error": "each device name must be a non-empty string",
                }
            if not isinstance(port, int):
                return {
                    "status": "error",
                    "error": f"port for device '{name}' must be an integer",
                }
            normalized[name.strip()] = {
                "host": "100.95.123.100",
                "port": port,
            }

        def write_devices() -> None:
            os.makedirs(os.path.dirname(DEVICES_FILE), exist_ok=True)
            with open(DEVICES_FILE, "w", encoding="utf-8") as f:
                json.dump(normalized, f, indent=2)

        await asyncio.to_thread(write_devices)

        return {
            "status": "success",
            "device_count": len(normalized),
            "devices": normalized,
            "path": DEVICES_FILE,
        }
    except Exception as e:
        logger.error(f"Failed to bootstrap devices: {e}")
        return {
            "status": "error",
            "error": str(e),
        }

# Tool: Get node details (including console host/port)


@mcp.tool
async def gns3_get_node(
    project_id: str,
    node_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """Get detailed node info, including console host/port."""
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        node = await client.get_node(project_id, node_id)
        return {
            "status": "success",
            "node": node,
        }
    except Exception as e:
        logger.error(f"Failed to get node: {e}")
        return {
            "status": "error",
            "error": str(e),
            "node_id": node_id
        }

# Tool: Delete a link


@mcp.tool
async def gns3_delete_link(
    project_id: str,
    link_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """Delete a link from a GNS3 project."""
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        result = await client.delete_link(project_id, link_id)

        return {
            "status": "success",
            "link_id": link_id,
            "deleted": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Failed to delete link: {e}")
        return {
            "status": "error",
            "error": str(e),
            "link_id": link_id
        }

# Tool: Get current network topology


@mcp.tool
async def gns3_get_topology(
    project_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """Get the current network topology for a project.

    Args:
        project_id: ID of the project
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication

    Returns:
        Dictionary containing topology information
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Get project, nodes, and links
        project = await client.get_project(project_id)
        nodes = await client.get_project_nodes(project_id)
        links = await client.get_project_links(project_id)

        # Build a quick lookup to recover node_type when formatting links
        node_lookup = {n.get("node_id"): n for n in nodes}

        def friendly_iface(node_id: str, link_node: Dict[str, Any]) -> str:
            """
            Derive a user-friendly interface label from adapter/port numbers.
            Rules mirror the add_link parsing:
            - IOSv/IOSvL3 (qemu) encodes GiX/Y as adapter = X*4+Y, port_number = 0.
            - IOU Ethernet keeps adapter=X, port=Y (map to E<X>/<Y>).
            - If port_name already present from the API, return it.
            - Fallback to adapter/port numbers if present, else "N/A".
            """
            # Use the API-provided port_name when present
            if link_node.get("port_name"):
                return str(link_node["port_name"])

            adapter = link_node.get("adapter_number")
            port = link_node.get("port_number")
            if adapter is None or port is None:
                return "N/A"

            node_type = (node_lookup.get(node_id) or {}).get("node_type", "")
            # Heuristic: qemu IOSv/IOSvL3 → treat as Gi with adapter = X*4+Y, port=0
            if node_type in {"qemu", "iou"}:
                # qemu IOSv/IOSvL3 encoding: adapter=N => Gi{N//4}/{N%4} when port==0
                if node_type == "qemu" and port == 0:
                    return f"Gi{adapter//4}/{adapter % 4}"
                # IOU Ethernet: adapter/port as E{adapter}/{port}
                if node_type == "iou":
                    return f"E{adapter}/{port}"

            # Generic fallback
            return f"{adapter}/{port}"

        # Format nodes summary
        nodes_summary = []
        for node in nodes:
            nodes_summary.append({
                "Node": node.get("name", "Unnamed"),
                "Status": node.get("status", "unknown"),
                "Console Port": node.get("console", "N/A"),
                "ID": node.get("node_id", ""),
                "Node Type": node.get("node_type", "unknown")
            })

        # Format links summary
        links_summary = []
        for link in links:
            node_a = next(
                (n for n in nodes if n["node_id"] == link["nodes"][0]["node_id"]), {})
            node_b = next(
                (n for n in nodes if n["node_id"] == link["nodes"][1]["node_id"]), {})

            node_a_ep = link["nodes"][0]
            node_b_ep = link["nodes"][1]

            links_summary.append({
                "link_id": link.get("link_id", ""),
                "Node A": node_a.get("name", "Unknown"),
                "Port A": friendly_iface(node_a_ep.get("node_id", ""), node_a_ep),
                "adapter_a": node_a_ep.get("adapter_number"),
                "port_a": node_a_ep.get("port_number"),
                "Node B": node_b.get("name", "Unknown"),
                "Port B": friendly_iface(node_b_ep.get("node_id", ""), node_b_ep),
                "adapter_b": node_b_ep.get("adapter_number"),
                "port_b": node_b_ep.get("port_number")
            })

        return {
            "status": "success",
            "project": {
                "project_id": project.get("project_id"),
                "name": project.get("name"),
                "status": project.get("status"),
                "stats": project.get("stats", {})
            },
            "nodes": nodes_summary,
            "links": links_summary,
            "topology_summary": {
                "total_nodes": len(nodes_summary),
                "total_links": len(links_summary),
                "node_types": list(set(node.get("Node Type", "unknown") for node in nodes_summary))
            }
        }
    except Exception as e:
        logger.error(f"Failed to get topology: {e}")
        return {
            "status": "error",
            "error": str(e),
            "project": None
        }

# Tool: Save project


@mcp.tool
async def gns3_save_project(
    project_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None,
    snapshot_name: Optional[str] = None
) -> Dict[str, Any]:
    """Save a GNS3 project.

    Args:
        project_id: ID of the project to save
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication
        snapshot_name: Optional name for a snapshot

    Returns:
        Dictionary containing save result
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Create snapshot if name provided
        snapshot_info = None
        if snapshot_name:
            snapshot = await client.create_snapshot(project_id, snapshot_name)
            snapshot_info = {
                "snapshot_id": snapshot.get("snapshot_id"),
                "name": snapshot_name,
                "created_at": snapshot.get("created_at")
            }

        # Get project status
        project = await client.get_project(project_id)

        return {
            "status": "success",
            "project_id": project_id,
            "project_saved": True,
            "snapshot": snapshot_info,
            "project_status": project.get("status", "unknown")
        }
    except Exception as e:
        logger.error(f"Failed to save project: {e}")
        return {
            "status": "error",
            "error": str(e),
            "project_id": project_id
        }

# Tool: Export project


@mcp.tool
async def gns3_export_project(
    project_id: str,
    export_path: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None,
    include_ios_images: bool = False,
    include_node_images: bool = False
) -> Dict[str, Any]:
    """Export a GNS3 project to a file.

    Args:
        project_id: ID of the project to export
        export_path: Path where to export the project
        server_url: GNS3 server URL
        username: Optional username for authentication
        password: Optional password for authentication
        include_ios_images: Include IOS images in export
        include_node_images: Include node images in export

    Returns:
        Dictionary containing export result
    """
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        # Note: GNS3 export is typically done through the web interface
        # This tool provides the export parameters that can be used
        export_params = {
            "path": export_path,
            "include_ios_images": include_ios_images,
            "include_node_images": include_node_images
        }

        # Get project info for confirmation
        project = await client.get_project(project_id)

        return {
            "status": "success",
            "project_id": project_id,
            "project_name": project.get("name"),
            "export_path": export_path,
            "export_params": export_params,
            "export_completed": True,
            "note": "Project export parameters prepared. Use GNS3 web interface for actual export."
        }
    except Exception as e:
        logger.error(f"Failed to export project: {e}")
        return {
            "status": "error",
            "error": str(e),
            "project_id": project_id
        }

# Tool: Update project properties


@mcp.tool
async def gns3_update_project(
    project_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None,
    auto_close: Optional[bool] = None,
    name: Optional[str] = None
) -> Dict[str, Any]:
    """Update project properties (e.g., auto_close, name)."""
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        payload: Dict[str, Any] = {}
        if auto_close is not None:
            payload["auto_close"] = auto_close
        if name is not None:
            payload["name"] = name
        if not payload:
            raise ValueError("No update fields provided.")

        updated = await client.update_project(project_id, payload)
        return {
            "status": "success",
            "project": updated
        }
    except Exception as e:
        logger.error(f"Failed to update project: {e}")
        return {
            "status": "error",
            "error": str(e),
            "project": None
        }

# Tool: Get project settings (includes auto_close)


@mcp.tool
async def gns3_get_project_settings(
    project_id: str,
    server_url: str = "http://localhost:3080",
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """Get project settings such as auto_close, name, status, and stats."""
    try:
        config = GNS3Config(server_url=server_url,
                            username=username, password=password)
        client = GNS3APIClient(config)

        project = await client.get_project(project_id)

        return {
            "status": "success",
            "project": {
                "project_id": project.get("project_id"),
                "name": project.get("name"),
                "status": project.get("status"),
                "auto_close": project.get("auto_close"),
                "stats": project.get("stats", {})
            }
        }
    except Exception as e:
        logger.error(f"Failed to get project settings: {e}")
        return {
            "status": "error",
            "error": str(e),
            "project": None
        }

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
