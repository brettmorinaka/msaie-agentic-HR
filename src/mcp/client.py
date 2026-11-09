import sys
import time
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool, StructuredTool

from src.config import MCP_TRANSPORT
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
    Client for interacting with Model Context Protocol (MCP) servers via stdio transport.
    Utilizes langchain-mcp-adapters and MultiServerMCPClient for subprocess stdio
    connection management and LangChain tool integration with operational telemetry.
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        prefer_http: bool = False,
        connections: Optional[Dict[str, Any]] = None
    ):
        self.server_url = server_url
        self.prefer_http = prefer_http
        self.call_history: List[ToolCallRecord] = []
        self._cached_tools: Optional[List[Dict[str, Any]]] = None
        self._langchain_tools: Optional[List[BaseTool]] = None

        # Build MultiServerMCPClient connection configurations exclusively using stdio transport
        if connections is not None:
            self.connections = connections
        else:
            self.connections = {
                "hr_mcp_server": {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": ["-m", "src.mcp.server"]
                }
            }

        # Initialize the langchain-mcp-adapters MultiServerMCPClient
        self.multi_server_client = MultiServerMCPClient(connections=self.connections)

    def is_server_reachable(self) -> bool:
        """Check if the MCP stdio server process is reachable and operational."""
        try:
            tools = self.list_tools()
            return len(tools) > 0
        except Exception:
            return False

    def get_langchain_tools(self) -> List[BaseTool]:
        """
        Retrieve all available tools converted to LangChain BaseTool objects.
        Discovers tools over the MCP stdio transport, falling back to FastMCP registry.
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
        """Discover tools from the MCP server using MultiServerMCPClient over stdio."""
        if self._cached_tools is not None:
            return self._cached_tools

        try:
            lc_tools = self.get_langchain_tools()
            if lc_tools:
                self._cached_tools = [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": getattr(t, "args_schema", None).schema() if getattr(t, "args_schema", None) else {}
                    }
                    for t in lc_tools
                ]
                return self._cached_tools
        except Exception:
            pass

        # Fallback to FastMCP tool definitions
        self._cached_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"]
            }
            for t in MCP_TOOL_DEFINITIONS
        ]
        return self._cached_tools

    @staticmethod
    def _extract_tool_result(raw_res: Any) -> Any:
        """Helper to extract structured payload from LangChain / MCP tool execution."""
        if isinstance(raw_res, tuple) and len(raw_res) > 1 and isinstance(raw_res[1], dict) and "structured_content" in raw_res[1]:
            return raw_res[1]["structured_content"].get("result")
        if isinstance(raw_res, tuple) and len(raw_res) > 0:
            first = raw_res[0]
            if isinstance(first, list) and len(first) > 0:
                item = first[0]
                text_val = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
                if text_val:
                    try:
                        return json.loads(text_val)
                    except Exception:
                        return text_val
            elif isinstance(first, dict) and "text" in first:
                try:
                    return json.loads(first["text"])
                except Exception:
                    return first["text"]
        if isinstance(raw_res, list) and len(raw_res) > 0:
            first = raw_res[0]
            text_val = first.get("text") if isinstance(first, dict) else getattr(first, "text", None)
            if text_val:
                try:
                    return json.loads(text_val)
                except Exception:
                    return text_val
        if isinstance(raw_res, str):
            try:
                return json.loads(raw_res)
            except Exception:
                return raw_res
        return raw_res

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool via the MCP stdio transport.
        Maintains operational telemetry, latency tracking, and action safety audit.
        """
        start_time = time.perf_counter()
        result = None
        status = "success"

        # Execute via stdio transport using MultiServerMCPClient tools
        try:
            lc_tools = self.get_langchain_tools()
            target_tool = next((t for t in lc_tools if t.name == tool_name), None)
            if target_tool:
                raw_res = target_tool.invoke(arguments)
                result = self._extract_tool_result(raw_res)
            elif tool_name in TOOL_MAP:
                result = TOOL_MAP[tool_name](**arguments)
            else:
                result = {"error": f"Tool '{tool_name}' not found in MCP registry"}
                status = "error"
        except Exception as e:
            # Fallback to direct tool execution if subprocess stdio encounters unexpected error
            if tool_name in TOOL_MAP:
                try:
                    result = TOOL_MAP[tool_name](**arguments)
                except Exception as inner_e:
                    result = {"error": f"Tool execution failed: {str(inner_e)}"}
                    status = "error"
            else:
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
        """Asynchronous execution of an MCP tool using MultiServerMCPClient over stdio."""
        start_time = time.perf_counter()
        status = "success"
        try:
            tools = await self.multi_server_client.get_tools()
            target_tool = next((t for t in tools if t.name == tool_name), None)
            if target_tool:
                raw = await target_tool.ainvoke(arguments)
                result = self._extract_tool_result(raw)
            elif tool_name in TOOL_MAP:
                result = TOOL_MAP[tool_name](**arguments)
            else:
                result = {"error": f"Tool '{tool_name}' not found in MCP registry"}
                status = "error"
        except Exception as e:
            if tool_name in TOOL_MAP:
                try:
                    result = TOOL_MAP[tool_name](**arguments)
                except Exception as inner_e:
                    result = {"error": f"Tool execution failed: {str(inner_e)}"}
                    status = "error"
            else:
                result = {"error": f"Tool execution failed: {str(e)}"}
                status = "error"

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
