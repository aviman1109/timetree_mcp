"""Provider abstractions for TimeTree account backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from timetree_multi_mcp.config import TimeTreeAccount
from timetree_multi_mcp.models import (
    CalendarSummary,
    EventCreateInput,
    EventSummary,
    EventUpdateInput,
)


class TimeTreeProviderError(RuntimeError):
    """Base provider error."""


class AuthenticationError(TimeTreeProviderError):
    """Raised when account authentication fails."""


class CapabilityError(TimeTreeProviderError):
    """Raised when a provider cannot support a requested operation."""


class NotFoundError(TimeTreeProviderError):
    """Raised when a calendar or event cannot be found."""


@dataclass(frozen=True)
class ProviderVerification:
    provider: str
    can_read: bool
    can_write: bool
    authenticated: bool
    mode: str
    account_label: str
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "can_read": self.can_read,
            "can_write": self.can_write,
            "authenticated": self.authenticated,
            "mode": self.mode,
            "account_label": self.account_label,
            "warnings": self.warnings,
            "details": self.details,
        }


class TimeTreeProvider(ABC):
    """Abstract provider interface for one configured account."""

    def __init__(self, account: TimeTreeAccount):
        self.account = account

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""

    @abstractmethod
    def verify_account(self) -> ProviderVerification:
        """Check credentials and report the provider's capabilities."""

    @abstractmethod
    def list_calendars(self) -> list[CalendarSummary]:
        """List calendars available to the configured account."""

    @abstractmethod
    def get_events(
        self,
        calendar_id: str,
        start_after: int | None = None,
        limit: int | None = None,
    ) -> list[EventSummary]:
        """Return events from the selected calendar."""

    @abstractmethod
    def get_updated_events(
        self,
        calendar_id: str,
        updated_after: int,
        limit: int | None = None,
    ) -> list[EventSummary]:
        """Return events updated after a timestamp."""

    @abstractmethod
    def create_event(self, calendar_id: str, event: EventCreateInput) -> EventSummary:
        """Create a new event."""

    @abstractmethod
    def update_event(
        self,
        calendar_id: str,
        event_uuid: str,
        event: EventUpdateInput,
    ) -> EventSummary:
        """Update an existing event."""

    @abstractmethod
    def delete_event(self, calendar_id: str, event_uuid: str) -> None:
        """Delete an event."""
