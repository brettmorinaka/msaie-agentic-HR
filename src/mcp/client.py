import time
import json
import httpx
from typing import Dict, Any, List, Optional
from src.config import MCP_SERVER_URL, MCP_TRANSPORT
from src.mcp.tools import MCP_TOOL_DEFINITIONS, TOOL_MAP

class ToolCallRecord:
    def __init__(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        output: Any,
        latency_ms: float,
        status: str = "success"
    ):
        self.tool_name = tool_name
        self.arguments = arguments
        self.output = output
        self.latency_ms = latency_ms
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "output": self.output,
            "latency_ms": round(self.latency_ms, 2),
            "status": self.status
        }


class MCPClient:
    """
    Client for interacting with the Model Context Protocol (MCP) server.
    Supports both HTTP network transport and in-process MCP protocol wrapping.
    """

    def __init__(self, server_url: str = MCP_SERVER_URL, prefer_http: bool = True):
        self.server_url = server_url
        self.prefer_http = prefer_http
        self.call_history: List[ToolCallRecord] = []
        self._cached_tools: Optional[List[Dict[str, Any]]] = None

    def is_server_reachable(self) -> bool:
        """Check if the remote MCP HTTP server is reachable."""
        try:
            health_url = self.server_url.replace("/mcp", "/health")
            with httpx.Client(timeout=1.5) as client:
                res = client.get(health_url)
                return res.status_code == 200
        except Exception:
            return False

    def list_tools(self) -> List[Dict[str, Any]]:
        """Discover tools from the MCP server."""
        if self._cached_tools is not None:
            return self._cached_tools

        # Try HTTP discovery first if enabled
        if self.prefer_http:
            try:
                tools_url = self.server_url.replace("/mcp", "/mcp/tools")
                with httpx.Client(timeout=2.0) as client:
                    res = client.get(tools_url)
                    if res.status_code == 200:
                        data = res.json()
                        self._cached_tools = data.get("tools", [])
                        return self._cached_tools
            except Exception:
                pass

        # Fallback to local MCP definitions
        self._cached_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"]
            }
            for t in MCP_TOOL_DEFINITIONS
        ]
        return self._cached_tools

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool via the MCP protocol.
        Maintains operational telemetry and latency tracking.
        """
        start_time = time.perf_counter()
        use_http = self.prefer_http and self.is_server_reachable()
        result = None
        status = "success"

        if use_http:
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": len(self.call_history) + 1,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(self.server_url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        if "result" in data:
                            content = data["result"].get("content", [])
                            if content and content[0].get("type") == "text":
                                try:
                                    result = json.loads(content[0]["text"])
                                except Exception:
                                    result = content[0]["text"]
                            if data["result"].get("isError"):
                                status = "error"
                        elif "error" in data:
                            result = {"error": data["error"].get("message", "Unknown error")}
                            status = "error"
                    else:
                        status = "error"
                        result = {"error": f"HTTP error {resp.status_code}"}
            except Exception as e:
                # If network fails midway, fallback to in-process dispatch
                use_http = False

        if not use_http:
            # MCP In-Process protocol invocation
            if tool_name not in TOOL_MAP:
                result = {"error": f"Tool '{tool_name}' not found in MCP registry"}
                status = "error"
            else:
                try:
                    result = TOOL_MAP[tool_name](**arguments)
                    if isinstance(result, dict) and result.get("status") == "CONFIRMATION_REQUIRED":
                        status = "confirmation_required"
                except Exception as e:
                    result = {"error": f"Tool execution failed: {str(e)}"}
                    status = "error"

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        record = ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            output=result,
            latency_ms=latency_ms,
            status=status
        )
        self.call_history.append(record)

        return {
            "tool_name": tool_name,
            "status": status,
            "output": result,
            "latency_ms": round(latency_ms, 2)
        }

    def get_trace(self) -> List[Dict[str, Any]]:
        """Return the complete trace of tool executions."""
        return [r.to_dict() for r in self.call_history]

    def clear_trace(self):
        """Reset the tool execution trace."""
        self.call_history.clear()
