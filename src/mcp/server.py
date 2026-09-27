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
from src.mcp.tools import MCP_TOOL_DEFINITIONS, TOOL_MAP

app = FastAPI(
    title="HR Automation MCP Server",
    description="Model Context Protocol (MCP) Server exposing tools for policy search, employee records, and workflow execution.",
    version="1.0.0"
)

@app.get("/health")
@app.get("/mcp/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "mcp-hr-tools",
        "protocol": "Model Context Protocol (MCP)",
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
                    "result": {
                        "content": [{"type": "text", "text": f"Tool execution failed: {str(e)}"}],
                        "isError": True
                    }
                })

        elif method == "ping":
            return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": {}})

        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method '{method}' not implemented"}
            }, status_code=400)

    # Simplified REST invocation: {"tool": "...", "arguments": {...}} or {"name": "...", "arguments": {...}}
    tool_name = body.get("name") or body.get("tool")
    arguments = body.get("arguments", {})

    if not tool_name:
        return JSONResponse({"error": "Missing 'name' or 'tool' in request"}, status_code=400)

    if tool_name not in TOOL_MAP:
        return JSONResponse({"error": f"Tool '{tool_name}' not found"}, status_code=404)

    try:
        result = TOOL_MAP[tool_name](**arguments)
        return JSONResponse({
            "tool": tool_name,
            "status": "success",
            "result": result
        })
    except Exception as e:
        return JSONResponse({
            "tool": tool_name,
            "status": "error",
            "error": str(e)
        }, status_code=500)


def start_server(host: str = MCP_SERVER_HOST, port: int = MCP_SERVER_PORT):
    print(f"[*] Starting MCP Server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
