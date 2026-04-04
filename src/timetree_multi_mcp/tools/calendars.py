"""Calendar MCP tools for TimeTree."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from timetree_multi_mcp.client_manager import TimeTreeClientManager


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def register_calendar_tools(app: FastMCP, manager: TimeTreeClientManager) -> FastMCP:
    """Register calendar tools."""

    @app.tool()
    async def list_calendars(account_id: str) -> str:
        """List active TimeTree calendars for one configured account."""

        provider = manager.get_provider(account_id)
        calendars = [calendar.to_dict() for calendar in provider.list_calendars()]
        return _json(
            {
                "account_id": account_id,
                "provider": provider.provider_name,
                "total": len(calendars),
                "calendars": calendars,
            }
        )

    return app
