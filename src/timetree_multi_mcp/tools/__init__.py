"""Tool registration for the TimeTree multi-account MCP server."""

from mcp.server.fastmcp import FastMCP

from timetree_multi_mcp.client_manager import TimeTreeClientManager
from timetree_multi_mcp.tools.accounts import register_account_tools
from timetree_multi_mcp.tools.calendars import register_calendar_tools
from timetree_multi_mcp.tools.events import register_event_tools


def register_tools(app: FastMCP, manager: TimeTreeClientManager) -> FastMCP:
    """Register the initial set of multi-account TimeTree tools."""

    register_account_tools(app, manager)
    register_calendar_tools(app, manager)
    register_event_tools(app, manager)
    return app
