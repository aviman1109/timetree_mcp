"""Account registry and provider cache for TimeTree MCP."""

from __future__ import annotations

from dataclasses import asdict

from timetree_multi_mcp.config import AppConfig, TimeTreeAccount
from timetree_multi_mcp.providers.base import ProviderVerification, TimeTreeProvider
from timetree_multi_mcp.providers.sdk_provider import SDKTimeTreeProvider
from timetree_multi_mcp.providers.web_provider import WebTimeTreeProvider


class TimeTreeClientManager:
    """Small in-memory cache of provider instances keyed by `account_id`."""

    def __init__(
        self,
        accounts: dict[str, TimeTreeAccount],
        app_config: AppConfig,
        default_account_id: str | None = None,
    ) -> None:
        self._accounts = accounts
        self._app_config = app_config
        self._default_account_id = default_account_id
        self._providers: dict[str, TimeTreeProvider] = {}

    def list_accounts(self) -> list[dict[str, object]]:
        return [
            {
                "account_id": account.account_id,
                "label": account.label,
                "provider": account.provider,
                "default_calendar_id": account.default_calendar_id,
            }
            for account in self._accounts.values()
        ]

    def get_account(self, account_id: str | None = None) -> TimeTreeAccount:
        resolved_id = account_id or self._default_account_id
        if not resolved_id:
            raise ValueError("account_id is required because no default account is configured")
        try:
            return self._accounts[resolved_id]
        except KeyError as err:
            available = ", ".join(sorted(self._accounts))
            raise ValueError(f"Unknown account_id '{resolved_id}'. Available: {available}") from err

    def get_provider(self, account_id: str | None = None, refresh: bool = False) -> TimeTreeProvider:
        account = self.get_account(account_id)
        if refresh:
            self._providers.pop(account.account_id, None)
        if account.account_id not in self._providers:
            self._providers[account.account_id] = self._build_provider(account)
        return self._providers[account.account_id]

    def account_status(self, account_id: str | None = None, refresh: bool = False) -> dict[str, object]:
        account = self.get_account(account_id)
        provider = self.get_provider(account.account_id, refresh=refresh)
        verification: ProviderVerification = provider.verify_account()
        return {
            **asdict(account),
            "verification": verification.to_dict(),
        }

    def _build_provider(self, account: TimeTreeAccount) -> TimeTreeProvider:
        if account.provider == "sdk":
            return SDKTimeTreeProvider(account, app_config=self._app_config)
        if account.provider == "web":
            return WebTimeTreeProvider(account, app_config=self._app_config)
        raise ValueError(
            f"Unsupported provider '{account.provider}' for account '{account.account_id}'"
        )
