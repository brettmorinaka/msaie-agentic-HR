import sys
import time
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool, StructuredTool

from src.config import MCP_SERVER_URL, MCP_TRANSPORT
from src.mcp.tools import mcp, MCP_TOOL_DEFINITIONS, TOOL_MAP


def _run_sync(coro):
    """Safely execute an async coroutine from synchronous contexts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()
    else:
        return asyncio.run(coro)


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
    Client for interacting with Model Context Protocol (MCP) servers.
    Utilizes langchain-mcp-adapters and MultiServerMCPClient for multi-server discovery,
    connection management, and LangChain tool integration with operational telemetry.
    """

    def __init__(
        self,
        server_url: str = MCP_SERVER_URL,
        prefer_http: bool = True,
        connections: Optional[Dict[str, Any]] = None
    ):
        self.server_url = server_url
        self.prefer_http = prefer_http
        self.call_history: List[ToolCallRecord] = []
        self._cached_tools: Optional[List[Dict[str, Any]]] = None
        self._langchain_tools: Optional[List[BaseTool]] = None

        # Build MultiServerMCPClient connection configurations
        if connections is not None:
            self.connections = connections
        elif self.prefer_http:
            base_url = self.server_url.rstrip("/")
            sse_url = f"{base_url}/sse/sse" if not base_url.endswith("/sse") else base_url
            self.connections = {
                "hr_mcp_server": {
                    "transport": "sse",
                    "url": sse_url
                }
            }
        else:
            self.connections = {
                "hr_mcp_server": {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": ["-m", "src.mcp.server", "--stdio"]
                }
            }

        # Initialize the langchain-mcp-adapters MultiServerMCPClient
        self.multi_server_client = MultiServerMCPClient(connections=self.connections)

    def is_server_reachable(self) -> bool:
        """Check if the remote MCP HTTP server is reachable."""
        try:
            health_url = self.server_url.replace("/mcp", "/health")
            with httpx.Client(timeout=1.5) as client:
                res = client.get(health_url)
                return res.status_code == 200
        except Exception:
            return False

    def get_langchain_tools(self) -> List[BaseTool]:
        """
        Retrieve all available tools converted to LangChain BaseTool objects.
        Attempts MultiServerMCPClient discovery first, falling back to FastMCP tool registry.
        """
        if self._langchain_tools is not None:
            return self._langchain_tools

        try:
            tools = _run_sync(self.multi_server_client.get_tools())
            if tools:
                wrapped_tools = []
                for t in tools:
                    if not getattr(t, "func", None) and getattr(t, "coroutine", None):
                        def make_sync(coro_fn):
                            return lambda *args, **kwargs: _run_sync(coro_fn(*args, **kwargs))
                        wrapped = StructuredTool(
                            name=t.name,
                            description=t.description,
                            args_schema=getattr(t, "args_schema", None),
                            func=make_sync(t.coroutine),
                            coroutine=t.coroutine
                        )
                        wrapped_tools.append(wrapped)
                    else:
                        wrapped_tools.append(t)
                self._langchain_tools = wrapped_tools
                return self._langchain_tools
        except Exception:
            pass

        # Convert local FastMCP tools into LangChain StructuredTools
        self._langchain_tools = [
            StructuredTool.from_function(
                func=t["handler"],
                name=t["name"],
                description=t["description"]
            )
            for t in MCP_TOOL_DEFINITIONS
        ]
        return self._langchain_tools

    def list_tools(self) -> List[Dict[str, Any]]:
        """Discover tools from the MCP server using MultiServerMCPClient or FastMCP registry."""
        if self._cached_tools is not None:
            return self._cached_tools

        # Try HTTP discovery first if enabled and reachable
        if self.prefer_http and self.is_server_reachable():
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

        # Return FastMCP tool definitions
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
        Maintains operational telemetry, latency tracking, and action safety audit.
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
            except Exception:
                # If network fails midway, fallback to in-process FastMCP dispatch
                use_http = False

        if not use_http:
            # FastMCP In-Process tool execution
            if tool_name not in TOOL_MAP:
                result = {"error": f"Tool '{tool_name}' not found in MCP registry"}
                status = "error"
            else:
                try:
                    result = TOOL_MAP[tool_name](**arguments)
                except Exception as e:
                    result = {"error": f"Tool execution failed: {str(e)}"}
                    status = "error"

        # Check action safety guardrail status
        if isinstance(result, dict) and result.get("status") == "CONFIRMATION_REQUIRED":
            status = "confirmation_required"

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

    async def acall_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Asynchronous execution of an MCP tool using MultiServerMCPClient."""
        start_time = time.perf_counter()
        status = "success"
        try:
            tools = await self.multi_server_client.get_tools()
            target_tool = next((t for t in tools if t.name == tool_name), None)
            if target_tool:
                raw = await target_tool.ainvoke(arguments)
                # Parse LangChain text content
                result = raw
                if isinstance(raw, list) and len(raw) > 0:
                    first = raw[0]
                    text_val = first.get("text") if isinstance(first, dict) else getattr(first, "text", None)
                    if text_val:
                        try:
                            result = json.loads(text_val)
                        except Exception:
                            result = text_val
            else:
                result = TOOL_MAP[tool_name](**arguments)
        except Exception:
            result = TOOL_MAP[tool_name](**arguments)

        if isinstance(result, dict) and result.get("status") == "CONFIRMATION_REQUIRED":
            status = "confirmation_required"

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
