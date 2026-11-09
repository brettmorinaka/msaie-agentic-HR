"""
Model Context Protocol (MCP) Server using FastMCP with Standard I/O (stdio) transport.
Communicates via standard input and standard output streams with MCP clients
(such as MultiServerMCPClient from langchain-mcp-adapters).
"""

import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.mcp.tools import mcp, MCP_TOOL_DEFINITIONS, TOOL_MAP


def run_server():
    """Start the FastMCP server using stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
