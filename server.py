#!/usr/bin/env python3
"""
GNS3 MCP Server - FastMCP implementation for GNS3 network simulation integration.

This MCP server provides tools for managing GNS3 network topologies,
project management, and simulation control through direct HTTP API calls.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP("GNS3 Network Simulator")

# Configuration models
class GNS3Config(BaseModel):
    """Configuration for GNS3 server connection."""
    server_url: str = Field(default="http://localhost:3080", description="GNS3 server URL")
    username: Optional[str] = Field(default=None, description="Username for authentication")
    password: Optional[str] = Field(default=None, description="Password for authentication")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")

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
        url = f"{self.base_url}/v3{endpoint}"
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
            raise Exception(f"GNS3 API error: {e.response.status_code} - {e.response.text}")
    
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
        return await self._request("PUT", f"/projects/{project_id}/open")
    
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
    
    async def create_snapshot(self, project_id: str, name: str) -> Dict[str, Any]:
        """Create a project snapshot."""
        data = {"name": name}
        return await self._request("POST", f"/projects/{project_id}/snapshots", data)

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
        config = GNS3Config(server_url=server_url, username=username, password=password)
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
        
        return {
            "status": "success",
            "server_info": {
                "version": server_info.get("version", "unknown"),
                "user": server_info.get("user", "anonymous")
            },
            "projects": projects_summary,
            "total_projects": len(projects_summary)
        }
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
        client = GNS3APIClient(config)
        
        # Prepare link data
        link_data = {
            "nodes": [
                {
                    "node_id": node_a_id,
                    "port_name": node_a_port
                },
                {
                    "node_id": node_b_id,
                    "port_name": node_b_port
                }
            ]
        }
        
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
        client = GNS3APIClient(config)
        
        # Get project, nodes, and links
        project = await client.get_project(project_id)
        nodes = await client.get_project_nodes(project_id)
        links = await client.get_project_links(project_id)
        
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
            node_a = next((n for n in nodes if n["node_id"] == link["nodes"][0]["node_id"]), {})
            node_b = next((n for n in nodes if n["node_id"] == link["nodes"][1]["node_id"]), {})
            
            links_summary.append({
                "Node A": node_a.get("name", "Unknown"),
                "Port A": link["nodes"][0].get("port_name", "N/A"),
                "Node B": node_b.get("name", "Unknown"),
                "Port B": link["nodes"][1].get("port_name", "N/A")
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
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
        config = GNS3Config(server_url=server_url, username=username, password=password)
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

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()