"""Server bootstrap for the multi-account TimeTree MCP."""

from __future__ import annotations

import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import uvicorn

from timetree_multi_mcp.client_manager import TimeTreeClientManager
from timetree_multi_mcp.config import load_accounts, load_app_config
from timetree_multi_mcp.tools import register_tools


SERVER_INSTRUCTIONS = """
This MCP server exposes TimeTree data for multiple pre-configured accounts.
Always call list_accounts first when you are unsure which account_id to use.
Every tool requires an explicit account_id so reads and writes stay scoped to the right person.
Use get_account_status to learn whether an account is using the SDK provider or the unofficial web provider.
""".strip()


def build_app() -> tuple[FastMCP, TimeTreeClientManager, object]:
    """Build the MCP app and account manager."""

    load_dotenv()
    runtime_config = load_app_config()
    accounts, config_default_account_id = load_accounts(runtime_config.accounts_file)
    manager = TimeTreeClientManager(
        accounts=accounts,
        app_config=runtime_config,
        default_account_id=runtime_config.default_account_id or config_default_account_id,
    )

    app = FastMCP(
        name="TimeTree Multi Account MCP",
        instructions=SERVER_INSTRUCTIONS,
    )
    app.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=runtime_config.allowed_hosts,
        allowed_origins=runtime_config.allowed_origins,
    )
    register_tools(app, manager)
    return app, manager, runtime_config


def main() -> None:
    """Run the server in stdio or remote HTTP mode."""

    try:
        app, manager, runtime_config = build_app()
    except Exception as err:
        print(f"Server bootstrap failed: {err}", file=sys.stderr)
        raise

    account_count = len(manager.list_accounts())
    print(
        f"Loaded {account_count} TimeTree account(s). Transport={runtime_config.transport}",
        file=sys.stderr,
    )

    if runtime_config.transport.lower() == "stdio":
        app.run()
        return

    transport = runtime_config.transport.lower()
    if transport in {"http", "streamable-http"}:
        http_app = app.streamable_http_app()
        uvicorn.run(http_app, host=runtime_config.host, port=runtime_config.port)
        return

    if transport == "sse":
        sse_app = app.sse_app(mount_path=runtime_config.path)
        uvicorn.run(sse_app, host=runtime_config.host, port=runtime_config.port)
        return

    raise ValueError(
        f"Unsupported transport '{runtime_config.transport}'. "
        "Use stdio, http, streamable-http, or sse."
    )


if __name__ == "__main__":
    main()
