import sys
import json
import uvicorn
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import MCP_SERVER_HOST, MCP_SERVER_PORT
from src.mcp.tools import mcp, MCP_TOOL_DEFINITIONS, TOOL_MAP

app = FastAPI(
    title="HR Automation FastMCP Server",
    description="Model Context Protocol (MCP) Server using FastMCP and langchain-mcp-adapters.",
    version="1.0.0"
)

# Mount FastMCP SSE transport app
app.mount("/sse", mcp.sse_app())

@app.get("/health")
@app.get("/mcp/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "mcp-hr-tools",
        "protocol": "Model Context Protocol (MCP) via FastMCP",
        "tools_count": len(MCP_TOOL_DEFINITIONS)
    }

@app.get("/mcp/tools")
async def list_tools():
    """Return available tools formatted according to the MCP specification."""
    tools = [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"]
        }
        for t in MCP_TOOL_DEFINITIONS
    ]
    return {"tools": tools}

@app.post("/mcp")
@app.post("/mcp/call")
async def handle_mcp_request(request: Request):
    """
    Standard MCP JSON-RPC 2.0 and REST dispatch endpoint.
    Handles:
    - tools/list
    - tools/call
    - Direct tool call payload { "name": ..., "arguments": ... }
    """
    body = await request.json()

    # JSON-RPC 2.0 style
    if isinstance(body, dict) and "jsonrpc" in body:
        method = body.get("method")
        msg_id = body.get("id", 1)
        params = body.get("params", {})

        if method == "tools/list":
            tools = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": t["inputSchema"]
                }
                for t in MCP_TOOL_DEFINITIONS
            ]
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": tools}
            })

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name not in TOOL_MAP:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}
                }, status_code=404)

            try:
                result = TOOL_MAP[tool_name](**arguments)
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps(result, default=str)}
                        ],
                        "isError": False
                    }
                })
            except Exception as e:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32000, "message": str(e)}
                }, status_code=500)

        elif method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "HR-Automation-MCP-Server",
                        "version": "1.0.0"
                    }
                }
            })

    # Direct REST dispatch
    elif isinstance(body, dict) and "name" in body:
        tool_name = body.get("name")
        arguments = body.get("arguments", {})

        if tool_name not in TOOL_MAP:
            return JSONResponse({"error": f"Tool '{tool_name}' not found"}, status_code=404)

        try:
            result = TOOL_MAP[tool_name](**arguments)
            return JSONResponse({"status": "success", "tool": tool_name, "result": result})
        except Exception as e:
            return JSONResponse({"status": "error", "tool": tool_name, "error": str(e)}, status_code=500)

    return JSONResponse({"error": "Invalid MCP request format"}, status_code=400)


def start_server(host: str = MCP_SERVER_HOST, port: int = MCP_SERVER_PORT):
    """Start the FastMCP HTTP and SSE server using uvicorn."""
    print(f"[*] Starting FastMCP Server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    if "--stdio" in sys.argv:
        # FastMCP native stdio runner for subprocess MCP clients
        mcp.run(transport="stdio")
    else:
        start_server()
