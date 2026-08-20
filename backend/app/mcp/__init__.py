"""SLP Pro's MCP server: the /mcp endpoint and the key that opens it."""

from app.mcp.auth import MCP_PATH, McpAuthMiddleware, McpPrincipal, current_principal
from app.mcp.server import mcp_asgi_app, mcp_server

__all__ = [
    "MCP_PATH",
    "McpAuthMiddleware",
    "McpPrincipal",
    "current_principal",
    "mcp_asgi_app",
    "mcp_server",
]
