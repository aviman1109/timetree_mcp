"""Shared data models used by TimeTree providers and MCP tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _drop_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    return value


@dataclass(frozen=True)
class CalendarMember:
    name: str
    role: str | None = None
    user_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(asdict(self))


@dataclass(frozen=True)
class CalendarSummary:
    id: str
    name: str
    alias_code: str | None = None
    description: str | None = None
    color: Any | None = None
    is_active: bool = True
    users: list[CalendarMember] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "alias_code": self.alias_code,
            "description": self.description,
            "color": self.color,
            "is_active": self.is_active,
            "users": [user.to_dict() for user in self.users],
        }


@dataclass(frozen=True)
class EventSummary:
    uuid: str
    title: str
    calendar_id: str
    start_at: int
    end_at: int
    all_day: bool
    start_timezone: str | None = None
    end_timezone: str | None = None
    label_id: int | None = None
    category: Any | None = None
    location: str | None = None
    note: str | None = None
    url: str | None = None
    created_at: int | None = None
    updated_at: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "uuid": self.uuid,
            "title": self.title,
            "calendar_id": self.calendar_id,
            "start_at": self.start_at,
            "start_timezone": self.start_timezone,
            "end_at": self.end_at,
            "end_timezone": self.end_timezone,
            "all_day": self.all_day,
            "label_id": self.label_id,
            "category": self.category,
            "location": self.location,
            "note": self.note,
            "url": self.url,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return _drop_none(payload)


@dataclass(frozen=True)
class EventCreateInput:
    title: str
    start_at: int
    end_at: int
    all_day: bool = False
    start_timezone: str = "UTC"
    end_timezone: str = "UTC"
    label_id: int | None = None
    category: Any | None = 1
    note: str | None = None
    location: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class EventUpdateInput:
    title: str | None = None
    start_at: int | None = None
    end_at: int | None = None
    all_day: bool | None = None
    start_timezone: str | None = None
    end_timezone: str | None = None
    label_id: int | None = None
    category: Any | None = None
    note: str | None = None
    location: str | None = None
    url: str | None = None


def event_create_input_from_args(args: dict[str, Any]) -> EventCreateInput:
    return EventCreateInput(
        title=str(args["title"]),
        start_at=int(args["start_at"]),
        end_at=int(args["end_at"]),
        all_day=bool(args.get("all_day", False)),
        start_timezone=str(args.get("start_timezone") or "UTC"),
        end_timezone=str(args.get("end_timezone") or "UTC"),
        label_id=int(args["label_id"]) if args.get("label_id") is not None else None,
        category=args.get("category", 1),
        note=args.get("note"),
        location=args.get("location"),
        url=args.get("url"),
    )


def event_update_input_from_args(args: dict[str, Any]) -> EventUpdateInput:
    return EventUpdateInput(
        title=args.get("title"),
        start_at=int(args["start_at"]) if args.get("start_at") is not None else None,
        end_at=int(args["end_at"]) if args.get("end_at") is not None else None,
        all_day=bool(args["all_day"]) if args.get("all_day") is not None else None,
        start_timezone=args.get("start_timezone"),
        end_timezone=args.get("end_timezone"),
        label_id=int(args["label_id"]) if args.get("label_id") is not None else None,
        category=args.get("category"),
        note=args.get("note"),
        location=args.get("location"),
        url=args.get("url"),
    )
