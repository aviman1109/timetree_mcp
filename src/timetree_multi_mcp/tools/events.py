"""Event MCP tools for TimeTree."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from timetree_multi_mcp.client_manager import TimeTreeClientManager
from timetree_multi_mcp.models import event_create_input_from_args, event_update_input_from_args


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _iso(ts_ms: int | None) -> str | None:
    if ts_ms is None:
        return None
    return (
        datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _event_dict(event: dict[str, Any]) -> dict[str, Any]:
    payload = dict(event)
    for key in ("start_at", "end_at", "created_at", "updated_at"):
        if key in payload:
            payload[f"{key}_iso"] = _iso(payload.get(key))
    return payload


def _validate_required(value: Any, name: str) -> None:
    if value is None or value == "":
        raise ValueError(f"{name} is required")


def register_event_tools(app: FastMCP, manager: TimeTreeClientManager) -> FastMCP:
    """Register event read/write tools."""

    @app.tool()
    async def get_events(
        account_id: str,
        calendar_id: str,
        start_after: int | None = None,
        limit: int | None = None,
    ) -> str:
        """Get events from a TimeTree calendar for one configured account."""

        _validate_required(account_id, "account_id")
        _validate_required(calendar_id, "calendar_id")
        provider = manager.get_provider(account_id)
        events = [
            _event_dict(event.to_dict())
            for event in provider.get_events(
                str(calendar_id),
                start_after=start_after,
                limit=limit,
            )
        ]
        return _json(
            {
                "account_id": account_id,
                "provider": provider.provider_name,
                "calendar_id": str(calendar_id),
                "total": len(events),
                "events": events,
            }
        )

    @app.tool()
    async def get_updated_events(
        account_id: str,
        calendar_id: str,
        updated_after: int,
        limit: int | None = None,
    ) -> str:
        """Get TimeTree events updated after a given timestamp."""

        _validate_required(account_id, "account_id")
        _validate_required(calendar_id, "calendar_id")
        provider = manager.get_provider(account_id)
        events = [
            _event_dict(event.to_dict())
            for event in provider.get_updated_events(
                str(calendar_id),
                updated_after=int(updated_after),
                limit=limit,
            )
        ]
        return _json(
            {
                "account_id": account_id,
                "provider": provider.provider_name,
                "calendar_id": str(calendar_id),
                "updated_after": int(updated_after),
                "updated_after_iso": _iso(int(updated_after)),
                "total": len(events),
                "events": events,
            }
        )

    @app.tool()
    async def create_event(
        account_id: str,
        calendar_id: str,
        title: str,
        start_at: int,
        end_at: int,
        all_day: bool = False,
        start_timezone: str = "UTC",
        end_timezone: str = "UTC",
        label_id: int | None = None,
        category: str | int | None = 1,
        note: str | None = None,
        location: str | None = None,
        url: str | None = None,
    ) -> str:
        """Create a new TimeTree event for one configured account."""

        provider = manager.get_provider(account_id)
        event_input = event_create_input_from_args(
            {
                "title": title,
                "start_at": start_at,
                "end_at": end_at,
                "all_day": all_day,
                "start_timezone": start_timezone,
                "end_timezone": end_timezone,
                "label_id": label_id,
                "category": category,
                "note": note,
                "location": location,
                "url": url,
            }
        )
        created = provider.create_event(str(calendar_id), event_input)
        return _json(
            {
                "account_id": account_id,
                "provider": provider.provider_name,
                "calendar_id": str(calendar_id),
                "event": _event_dict(created.to_dict()),
            }
        )

    @app.tool()
    async def update_event(
        account_id: str,
        calendar_id: str,
        event_uuid: str,
        title: str | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        all_day: bool | None = None,
        start_timezone: str | None = None,
        end_timezone: str | None = None,
        label_id: int | None = None,
        category: str | int | None = None,
        note: str | None = None,
        location: str | None = None,
        url: str | None = None,
    ) -> str:
        """Update an existing TimeTree event for one configured account."""

        provider = manager.get_provider(account_id)
        event_input = event_update_input_from_args(
            {
                "title": title,
                "start_at": start_at,
                "end_at": end_at,
                "all_day": all_day,
                "start_timezone": start_timezone,
                "end_timezone": end_timezone,
                "label_id": label_id,
                "category": category,
                "note": note,
                "location": location,
                "url": url,
            }
        )
        updated = provider.update_event(str(calendar_id), event_uuid, event_input)
        return _json(
            {
                "account_id": account_id,
                "provider": provider.provider_name,
                "calendar_id": str(calendar_id),
                "event_uuid": event_uuid,
                "event": _event_dict(updated.to_dict()),
            }
        )

    @app.tool()
    async def delete_event(account_id: str, calendar_id: str, event_uuid: str) -> str:
        """Delete a TimeTree event for one configured account."""

        provider = manager.get_provider(account_id)
        provider.delete_event(str(calendar_id), event_uuid)
        return _json(
            {
                "account_id": account_id,
                "provider": provider.provider_name,
                "calendar_id": str(calendar_id),
                "deleted_event_uuid": event_uuid,
                "success": True,
            }
        )

    return app
