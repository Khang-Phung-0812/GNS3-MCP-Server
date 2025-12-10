import os
import json
import logging
import traceback

from fastapi import FastAPI, Request
from fastmcp import FastMCP
import uvicorn

# Disable fastmcp logs on stdout
logging.basicConfig(level=logging.CRITICAL)

# Import your existing MCP server definition (which contains all tools)
from server import mcp   # <-- this loads your MCP tools correctly


app = FastAPI()


@app.post("/mcp")
async def mcp_http(request: Request):
    """
    HTTP wrapper for MCP (JSON-RPC 2.0).
    """
    try:
        body = await request.json()

        # FastMCP uses `.dispatch()` for JSON-RPC handling
        response = await mcp.dispatch(body)

        return response

    except Exception as e:
        traceback.print_exc()
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32000,
                "message": str(e),
            },
            "id": None,
        }


if __name__ == "__main__":
    uvicorn.run(
        "server_http:app",
        host="0.0.0.0",
        port=9090,
        reload=False,
        access_log=False
    )
