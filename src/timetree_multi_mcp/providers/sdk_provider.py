"""TimeTree provider backed by the Python SDK."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from timetree_multi_mcp.config import AppConfig, TimeTreeAccount, resolve_value
from timetree_multi_mcp.models import (
    CalendarMember,
    CalendarSummary,
    EventCreateInput,
    EventSummary,
    EventUpdateInput,
)
from timetree_multi_mcp.providers.base import (
    AuthenticationError,
    NotFoundError,
    ProviderVerification,
    TimeTreeProvider,
)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sdk_category(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return "schedule"


class SDKTimeTreeProvider(TimeTreeProvider):
    """Provider using the legacy official TimeTree Python SDK."""

    def __init__(self, account: TimeTreeAccount, app_config: AppConfig):
        super().__init__(account)
        self._app_config = app_config
        self._sdk_loaded = False
        self._api_client: Any | None = None
        self._sdk_classes: dict[str, Any] = {}

    @property
    def provider_name(self) -> str:
        return "sdk"

    def verify_account(self) -> ProviderVerification:
        api = self._get_api_client()
        current_user = api.get_current_user()
        user_name = getattr(getattr(current_user, "data", None), "attributes", None)
        display_name = getattr(user_name, "name", None)
        return ProviderVerification(
            provider=self.provider_name,
            can_read=True,
            can_write=True,
            authenticated=True,
            mode="legacy-official-api",
            account_label=self.account.label,
            warnings=[
                "The official TimeTree API was shut down for new integrations in 2023; SDK access may stop working unexpectedly.",
                "SDK-backed event listing is approximated with upcoming_events and may not include historical items.",
            ],
            details={
                "user_name": display_name,
                "default_calendar_id": self.account.default_calendar_id,
            },
        )

    def list_calendars(self) -> list[CalendarSummary]:
        api = self._get_api_client()
        response = api.get_calendars()
        calendars = getattr(response, "data", []) or []
        results: list[CalendarSummary] = []
        for item in calendars:
            calendar_id = str(getattr(item, "id"))
            members = self._get_members(calendar_id)
            attributes = getattr(item, "attributes", None)
            results.append(
                CalendarSummary(
                    id=calendar_id,
                    name=getattr(attributes, "name", calendar_id),
                    description=getattr(attributes, "description", None),
                    color=getattr(attributes, "color", None),
                    is_active=True,
                    users=members,
                )
            )
        return results

    def get_events(
        self,
        calendar_id: str,
        start_after: int | None = None,
        limit: int | None = None,
    ) -> list[EventSummary]:
        api = self._get_api_client()
        response = api.get_upcoming_events(calendar_id, timezone="UTC", days=3650)
        raw_events = getattr(response, "data", []) or []
        events = [self._normalize_event(item, calendar_id) for item in raw_events]
        if start_after is not None:
            events = [event for event in events if event.start_at > start_after]
        events.sort(key=lambda item: item.start_at)
        if limit is not None:
            events = events[:limit]
        return events

    def get_updated_events(
        self,
        calendar_id: str,
        updated_after: int,
        limit: int | None = None,
    ) -> list[EventSummary]:
        events = [
            event
            for event in self.get_events(calendar_id)
            if event.updated_at is not None and event.updated_at > updated_after
        ]
        if limit is not None:
            events = events[:limit]
        return events

    def create_event(self, calendar_id: str, event: EventCreateInput) -> EventSummary:
        api = self._get_api_client()
        sdk_event = self._build_sdk_event(event)
        response = api.create_event(calendar_id, sdk_event)
        return self._normalize_event(getattr(response, "data"), calendar_id)

    def update_event(
        self,
        calendar_id: str,
        event_uuid: str,
        event: EventUpdateInput,
    ) -> EventSummary:
        api = self._get_api_client()
        sdk_event = self._build_sdk_event(event, allow_partial=True)
        response = api.update_event(calendar_id, event_uuid, sdk_event)
        return self._normalize_event(getattr(response, "data"), calendar_id)

    def delete_event(self, calendar_id: str, event_uuid: str) -> None:
        api = self._get_api_client()
        status_code = api.delete_event(calendar_id, event_uuid)
        if int(status_code) != 204:
            raise RuntimeError(f"Unexpected status code while deleting event: {status_code}")

    def _get_members(self, calendar_id: str) -> list[CalendarMember]:
        api = self._get_api_client()
        response = api.get_calendar_members(calendar_id)
        members = getattr(response, "data", []) or []
        results: list[CalendarMember] = []
        for member in members:
            attributes = getattr(member, "attributes", None)
            results.append(
                CalendarMember(
                    name=getattr(attributes, "name", str(getattr(member, "id", "unknown"))),
                    role=None,
                    user_id=str(getattr(member, "id", "")) or None,
                )
            )
        return results

    def _normalize_event(self, data: Any, calendar_id: str) -> EventSummary:
        if data is None:
            raise NotFoundError("Event payload was empty")

        attributes = getattr(data, "attributes", None)
        relationships = getattr(data, "relationships", None)
        label = getattr(relationships, "label", None)
        label_data = getattr(label, "data", None)
        label_id = _as_int(getattr(label_data, "id", None))
        event_id = str(getattr(data, "id", ""))

        return EventSummary(
            uuid=event_id,
            title=getattr(attributes, "title", ""),
            calendar_id=str(calendar_id),
            start_at=int(getattr(attributes, "start_at")),
            end_at=int(getattr(attributes, "end_at")),
            all_day=bool(getattr(attributes, "all_day", False)),
            start_timezone=getattr(attributes, "start_timezone", None),
            end_timezone=getattr(attributes, "end_timezone", None),
            label_id=label_id,
            category=getattr(attributes, "category", None),
            location=getattr(attributes, "location", None),
            note=getattr(attributes, "description", None),
            url=getattr(attributes, "url", None),
            created_at=_as_int(getattr(attributes, "created_at", None)),
            updated_at=_as_int(getattr(attributes, "updated_at", None)),
        )

    def _build_sdk_event(self, event: EventCreateInput | EventUpdateInput, allow_partial: bool = False) -> Any:
        self._ensure_sdk_loaded()
        Event = self._sdk_classes["Event"]
        EventData = self._sdk_classes["EventData"]
        EventAttributes = self._sdk_classes["EventAttributes"]
        EventRelationships = self._sdk_classes["EventRelationships"]
        EventRelationshipsLabel = self._sdk_classes["EventRelationshipsLabel"]
        EventRelationshipsLabelData = self._sdk_classes["EventRelationshipsLabelData"]

        label = None
        if event.label_id is not None:
            label = EventRelationshipsLabel(
                data=EventRelationshipsLabelData(id=str(event.label_id), type="label")
            )

        attributes_kwargs: dict[str, Any] = {
            "title": event.title,
            "category": _sdk_category(getattr(event, "category", None)),
            "all_day": event.all_day,
            "start_at": event.start_at,
            "end_at": event.end_at,
            "start_timezone": event.start_timezone,
            "end_timezone": event.end_timezone,
            "description": getattr(event, "note", None),
            "location": getattr(event, "location", None),
            "url": getattr(event, "url", None),
        }
        if allow_partial:
            attributes_kwargs = {key: value for key, value in attributes_kwargs.items() if value is not None}

        return Event(
            data=EventData(
                attributes=EventAttributes(**attributes_kwargs),
                relationships=EventRelationships(label=label),
            )
        )

    def _get_api_client(self) -> Any:
        if self._api_client is not None:
            return self._api_client

        self._ensure_sdk_loaded()
        access_token = resolve_value(self.account.access_token, self.account.access_token_file, self.account.access_token_env)
        if not access_token:
            raise AuthenticationError(
                f"SDK account '{self.account.account_id}' is missing access_token or access_token_file"
            )

        api_cls = self._sdk_classes["TimeTreeApi"]
        self._api_client = api_cls(access_token)
        try:
            self._api_client.get_current_user()
        except Exception as err:  # pragma: no cover - depends on remote API
            raise AuthenticationError(
                f"Failed to authenticate SDK account '{self.account.account_id}': {err}"
            ) from err
        return self._api_client

    def _ensure_sdk_loaded(self) -> None:
        if self._sdk_loaded:
            return

        default_sdk_path = Path(__file__).resolve().parents[4] / "timetree-sdk-python"
        candidate_path = Path(self._app_config.sdk_path) if self._app_config.sdk_path else default_sdk_path
        try:
            self._sdk_classes["TimeTreeApi"] = importlib.import_module("timetree_sdk.api").TimeTreeApi
            events_mod = importlib.import_module("timetree_sdk.models.events")
        except ModuleNotFoundError:
            if candidate_path.exists():
                sys.path.insert(0, str(candidate_path))
                self._sdk_classes["TimeTreeApi"] = importlib.import_module("timetree_sdk.api").TimeTreeApi
                events_mod = importlib.import_module("timetree_sdk.models.events")
            else:
                raise AuthenticationError(
                    "Unable to import timetree_sdk. Install it or set TIMETREE_SDK_PATH."
                )

        self._sdk_classes["Event"] = events_mod.Event
        self._sdk_classes["EventData"] = events_mod.EventData
        self._sdk_classes["EventAttributes"] = events_mod.EventAttributes
        self._sdk_classes["EventRelationships"] = events_mod.EventRelationships
        self._sdk_classes["EventRelationshipsLabel"] = events_mod.EventRelationshipsLabel
        self._sdk_classes["EventRelationshipsLabelData"] = events_mod.EventRelationshipsLabelData
        self._sdk_loaded = True
