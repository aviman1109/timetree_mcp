"""Account-scoped MCP tools for TimeTree."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from timetree_multi_mcp.client_manager import TimeTreeClientManager


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def register_account_tools(app: FastMCP, manager: TimeTreeClientManager) -> FastMCP:
    """Register account discovery and verification tools."""

    @app.tool()
    async def list_accounts() -> str:
        """List account IDs available to this TimeTree MCP server."""

        return _json({"accounts": manager.list_accounts()})

    @app.tool()
    async def get_account_status(account_id: str, refresh: bool = False) -> str:
        """Verify one configured TimeTree account and report provider capabilities."""

        return _json(manager.account_status(account_id, refresh=refresh))

    return app
