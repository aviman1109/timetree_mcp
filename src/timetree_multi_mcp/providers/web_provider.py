"""TimeTree provider backed by the unofficial web API."""

from __future__ import annotations

import re
import time
from dataclasses import asdict
from typing import Any
from uuid import uuid4

import requests

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
    TimeTreeProviderError,
)


BASE_URL = "https://timetreeapp.com/api/v1"
WEB_ROOT = "https://timetreeapp.com/"
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "X-Timetreea": "web/2.1.0/en",
}


class _RateLimiter:
    def __init__(self, max_requests_per_second: int):
        self.max_requests_per_second = max_requests_per_second
        self.tokens = float(max_requests_per_second)
        self.refill_rate = float(max_requests_per_second)
        self.last_refill = time.monotonic()

    def wait_for_token(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(
            float(self.max_requests_per_second),
            self.tokens + (elapsed * self.refill_rate),
        )
        self.last_refill = now

        if self.tokens >= 1:
            self.tokens -= 1
            return

        sleep_seconds = (1 - self.tokens) / self.refill_rate
        time.sleep(sleep_seconds)
        self.wait_for_token()


class WebTimeTreeProvider(TimeTreeProvider):
    """Provider using the reverse-engineered TimeTree web API."""

    def __init__(self, account: TimeTreeAccount, app_config: AppConfig):
        super().__init__(account)
        self._app_config = app_config
        self._session = requests.Session()
        self._csrf_token: str | None = None
        self._authenticated = False
        self._rate_limiter = _RateLimiter(app_config.web_max_requests_per_second)
        self._timeout = app_config.web_timeout_seconds

    @property
    def provider_name(self) -> str:
        return "web"

    def verify_account(self) -> ProviderVerification:
        self._ensure_authenticated()
        calendars = self.list_calendars()
        return ProviderVerification(
            provider=self.provider_name,
            can_read=True,
            can_write=self._csrf_token is not None,
            authenticated=self._authenticated,
            mode="unofficial-web-api",
            account_label=self.account.label,
            warnings=[
                "This provider depends on unofficial reverse-engineered TimeTree web endpoints.",
                "TimeTree can change authentication, CSRF handling, or event payloads without notice.",
            ],
            details={
                "calendar_count": len(calendars),
                "has_csrf_token": self._csrf_token is not None,
                "default_calendar_id": self.account.default_calendar_id,
            },
        )

    def list_calendars(self) -> list[CalendarSummary]:
        payload = self._request_json("GET", f"{BASE_URL}/calendars?since=0")
        calendars = payload.get("calendars", [])
        results: list[CalendarSummary] = []
        for item in calendars:
            if item.get("deactivated_at"):
                continue
            users = [
                CalendarMember(
                    name=str(user.get("name") or user.get("user_id") or "unknown"),
                    role="owner" if user.get("role") == 1 else "member",
                    user_id=str(user.get("user_id")) if user.get("user_id") is not None else None,
                )
                for user in item.get("calendar_users", []) or []
                if not user.get("deactivated_at")
            ]
            results.append(
                CalendarSummary(
                    id=str(item["id"]),
                    name=str(item.get("name") or item["id"]),
                    alias_code=item.get("alias_code"),
                    description=item.get("purpose"),
                    color=item.get("color"),
                    is_active=True,
                    users=users,
                )
            )
        return results

    def get_events(
        self,
        calendar_id: str,
        start_after: int | None = None,
        limit: int | None = None,
    ) -> list[EventSummary]:
        events = self._sync_events(calendar_id)
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
        payload = self._request_json("GET", f"{BASE_URL}/calendar/{calendar_id}/events?since={updated_after}")
        events = [
            self._normalize_event(item)
            for item in payload.get("events", []) or []
            if item.get("updated_at") and int(item["updated_at"]) > updated_after
        ]
        events.sort(key=lambda item: item.updated_at or 0, reverse=True)
        if limit is not None:
            events = events[:limit]
        return events

    def create_event(self, calendar_id: str, event: EventCreateInput) -> EventSummary:
        body = {
            "title": event.title,
            "all_day": event.all_day,
            "start_at": event.start_at,
            "start_timezone": event.start_timezone,
            "end_at": event.end_at,
            "end_timezone": event.end_timezone,
            "label_id": event.label_id,
            "category": event.category if event.category is not None else 1,
            "note": event.note,
            "location": event.location,
            "url": event.url,
            "recurrences": [],
            "alerts": [],
            "file_uuids": [],
        }
        payload = self._request_json(
            "POST",
            f"{BASE_URL}/calendar/{calendar_id}/event",
            json_body={key: value for key, value in body.items() if value is not None},
            requires_csrf=True,
        )
        return self._normalize_event(payload["event"])

    def update_event(
        self,
        calendar_id: str,
        event_uuid: str,
        event: EventUpdateInput,
    ) -> EventSummary:
        body = {
            "title": event.title,
            "all_day": event.all_day,
            "start_at": event.start_at,
            "start_timezone": event.start_timezone,
            "end_at": event.end_at,
            "end_timezone": event.end_timezone,
            "label_id": event.label_id,
            "category": event.category,
            "note": event.note,
            "location": event.location,
            "url": event.url,
        }
        payload = self._request_json(
            "PUT",
            f"{BASE_URL}/calendar/{calendar_id}/event/{event_uuid}",
            json_body={key: value for key, value in body.items() if value is not None},
            requires_csrf=True,
        )
        return self._normalize_event(payload["event"])

    def delete_event(self, calendar_id: str, event_uuid: str) -> None:
        target = None
        for event in self.get_events(calendar_id):
            if event.uuid == event_uuid:
                target = event
                break
        if target is None:
            raise NotFoundError(f"Event not found: {event_uuid}")

        delete_body = target.raw or target.to_dict()
        self._request_json(
            "DELETE",
            f"{BASE_URL}/calendar/{calendar_id}/event/{event_uuid}",
            json_body=delete_body,
            requires_csrf=True,
        )

    def _sync_events(self, calendar_id: str, since: int = 0) -> list[EventSummary]:
        payload = self._request_json("GET", f"{BASE_URL}/calendar/{calendar_id}/events/sync?since={since}")
        events = [self._normalize_event(item) for item in payload.get("events", []) or []]
        if payload.get("chunk") and int(payload.get("since", since)) > since:
            events.extend(self._sync_events(calendar_id, int(payload["since"])))
        return events

    def _normalize_event(self, data: dict[str, Any]) -> EventSummary:
        return EventSummary(
            uuid=str(data.get("uuid") or data.get("id")),
            title=str(data.get("title") or ""),
            calendar_id=str(data.get("calendar_id")),
            start_at=int(data.get("start_at")),
            end_at=int(data.get("end_at")),
            all_day=bool(data.get("all_day", False)),
            start_timezone=data.get("start_timezone"),
            end_timezone=data.get("end_timezone"),
            label_id=int(data["label_id"]) if data.get("label_id") is not None else None,
            category=data.get("category"),
            location=data.get("location"),
            note=data.get("note"),
            url=data.get("url"),
            created_at=int(data["created_at"]) if data.get("created_at") is not None else None,
            updated_at=int(data["updated_at"]) if data.get("updated_at") is not None else None,
            raw=dict(data),
        )

    def _ensure_authenticated(self) -> None:
        if self._authenticated and self._session.cookies.get("_session_id"):
            return

        email = resolve_value(self.account.email, self.account.email_file, self.account.email_env)
        password = resolve_value(self.account.password, self.account.password_file, self.account.password_env)
        if not email or not password:
            raise AuthenticationError(
                f"Web account '{self.account.account_id}' is missing email/password configuration"
            )

        auth_payload = {
            "uid": email,
            "password": password,
            "uuid": uuid4().hex,
        }
        self._rate_limiter.wait_for_token()
        response = self._session.put(
            f"{BASE_URL}/auth/email/signin",
            headers=DEFAULT_HEADERS,
            json=auth_payload,
            timeout=self._timeout,
        )
        if response.status_code == 401:
            raise AuthenticationError("Invalid TimeTree email or password")
        if response.status_code >= 400:
            raise AuthenticationError(
                f"TimeTree authentication failed with status {response.status_code}: {response.text}"
            )
        if not self._session.cookies.get("_session_id"):
            raise AuthenticationError("Authentication succeeded but no TimeTree session cookie was returned")

        self._csrf_token = self._fetch_csrf_token()
        self._authenticated = True

    def _fetch_csrf_token(self) -> str | None:
        self._rate_limiter.wait_for_token()
        response = self._session.get(WEB_ROOT, timeout=self._timeout)
        if response.status_code >= 400:
            return None
        match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', response.text, re.I)
        return match.group(1) if match else None

    def _request_json(
        self,
        method: str,
        url: str,
        json_body: dict[str, Any] | None = None,
        requires_csrf: bool = False,
    ) -> dict[str, Any]:
        self._ensure_authenticated()
        headers = dict(DEFAULT_HEADERS)
        if requires_csrf:
            if not self._csrf_token:
                self._csrf_token = self._fetch_csrf_token()
            if not self._csrf_token:
                raise AuthenticationError("CSRF token is required for write operations but could not be fetched")
            headers["x-csrf-token"] = self._csrf_token

        self._rate_limiter.wait_for_token()
        response = self._session.request(
            method=method,
            url=url,
            headers=headers,
            json=json_body,
            timeout=self._timeout,
        )

        if response.status_code == 401:
            self._authenticated = False
            raise AuthenticationError("TimeTree session expired or authentication failed")
        if response.status_code == 403:
            self._authenticated = False
            raise AuthenticationError("TimeTree rejected the request, likely due to CSRF or session state")
        if response.status_code == 404:
            raise NotFoundError(f"TimeTree resource not found: {url}")
        if response.status_code == 429:
            time.sleep(1)
            return self._request_json(method, url, json_body=json_body, requires_csrf=requires_csrf)
        if response.status_code >= 400:
            raise TimeTreeProviderError(
                f"TimeTree request failed with status {response.status_code}: {response.text}"
            )

        if not response.text:
            return {}
        try:
            return response.json()
        except ValueError as err:
            raise TimeTreeProviderError(
                f"Expected JSON response from TimeTree but received: {response.text[:200]}"
            ) from err
