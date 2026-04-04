"""Configuration helpers for the multi-account TimeTree MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml


ProviderType = Literal["sdk", "web"]


@dataclass(frozen=True)
class TimeTreeAccount:
    """Static account configuration loaded from YAML."""

    account_id: str
    label: str
    provider: ProviderType
    default_calendar_id: str | None = None
    access_token: str | None = None
    access_token_file: str | None = None
    access_token_env: str | None = None
    email: str | None = None
    email_file: str | None = None
    email_env: str | None = None
    password: str | None = None
    password_file: str | None = None
    password_env: str | None = None


@dataclass(frozen=True)
class AppConfig:
    """Application configuration loaded from environment."""

    accounts_file: str
    default_account_id: str | None
    transport: str
    host: str
    port: int
    path: str
    allowed_hosts: list[str]
    allowed_origins: list[str]
    sdk_path: str | None
    web_timeout_seconds: int
    web_max_requests_per_second: int


def resolve_value(raw: str | None, file_path: str | None, env_var: str | None = None) -> str | None:
    """Resolve a value directly, from a file path, or from an environment variable."""

    sources = sum(1 for s in (raw, file_path, env_var) if s)
    if sources > 1:
        raise ValueError("Only one of direct value, file path, and env var may be provided")
    if env_var:
        return os.environ.get(env_var) or None
    if file_path:
        return Path(os.path.expanduser(file_path)).read_text().rstrip()
    return raw


def _parse_csv_env(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_account(raw: dict[str, Any]) -> TimeTreeAccount:
    account_id = str(raw["account_id"]).strip()
    if not account_id:
        raise ValueError("Account configuration contains an empty account_id")

    provider = str(raw.get("provider") or "web").strip().lower()
    if provider not in {"sdk", "web"}:
        raise ValueError(
            f"Account '{account_id}' has unsupported provider '{provider}'. Use 'sdk' or 'web'."
        )

    label = str(raw.get("label") or account_id).strip()
    return TimeTreeAccount(
        account_id=account_id,
        label=label,
        provider=provider,  # type: ignore[arg-type]
        default_calendar_id=str(raw["default_calendar_id"])
        if raw.get("default_calendar_id") is not None
        else None,
        access_token=raw.get("access_token"),
        access_token_file=raw.get("access_token_file"),
        access_token_env=raw.get("access_token_env"),
        email=raw.get("email"),
        email_file=raw.get("email_file"),
        email_env=raw.get("email_env"),
        password=raw.get("password"),
        password_file=raw.get("password_file"),
        password_env=raw.get("password_env"),
    )


def load_accounts(accounts_file: str) -> tuple[dict[str, TimeTreeAccount], str | None]:
    """Load the multi-account registry from YAML."""

    config_path = Path(os.path.expanduser(accounts_file))
    if not config_path.exists():
        raise FileNotFoundError(
            f"Accounts configuration not found: {config_path}. "
            "Create it from config/accounts.example.yaml."
        )

    data = yaml.safe_load(config_path.read_text()) or {}
    raw_accounts = data.get("accounts") or []
    if not raw_accounts:
        raise ValueError(f"No accounts configured in {config_path}")

    accounts: dict[str, TimeTreeAccount] = {}
    for raw in raw_accounts:
        account = _normalize_account(raw)
        if account.account_id in accounts:
            raise ValueError(f"Duplicate account_id '{account.account_id}' in {config_path}")
        accounts[account.account_id] = account

    default_account_id = data.get("default_account_id")
    if default_account_id and default_account_id not in accounts:
        raise ValueError(
            f"default_account_id '{default_account_id}' is not present in accounts list"
        )

    return accounts, default_account_id


def load_app_config() -> AppConfig:
    """Load runtime configuration from environment variables."""

    default_allowed_hosts = [
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
    ]
    default_allowed_origins = [
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
    ]

    return AppConfig(
        accounts_file=os.getenv("TIMETREE_ACCOUNTS_FILE", "config/accounts.yaml"),
        default_account_id=os.getenv("TIMETREE_DEFAULT_ACCOUNT_ID") or None,
        transport=os.getenv("MCP_TRANSPORT", "stdio"),
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        path=os.getenv("MCP_PATH", "/mcp"),
        allowed_hosts=default_allowed_hosts + _parse_csv_env(os.getenv("MCP_ALLOWED_HOSTS")),
        allowed_origins=default_allowed_origins + _parse_csv_env(
            os.getenv("MCP_ALLOWED_ORIGINS")
        ),
        sdk_path=os.getenv("TIMETREE_SDK_PATH") or None,
        web_timeout_seconds=int(os.getenv("TIMETREE_WEB_TIMEOUT_SECONDS", "60")),
        web_max_requests_per_second=int(
            os.getenv("TIMETREE_WEB_MAX_REQUESTS_PER_SECOND", "10")
        ),
    )
