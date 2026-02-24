"""CoinGecko plugin tools — works both as imported plugin and standalone."""

from __future__ import annotations

import os
from typing import Any

try:
    from ai_v2.plugin_sdk import plugin_tool, secret
except ImportError:

    def plugin_tool(*, name: str | None = None):  # type: ignore[misc]
        def decorator(fn: Any) -> Any:
            fn.__plugin_tool__ = name or fn.__name__
            return fn
        return decorator

    def secret(key: str, default: str | None = None) -> str:  # type: ignore[misc]
        val = os.environ.get(key)
        if val:
            return val
        if default is not None:
            return default
        raise KeyError(f"Missing env var '{key}'")

from .client import CoinGeckoClient


def _client() -> CoinGeckoClient:
    return CoinGeckoClient(api_key=secret("COINGECKO_API_KEY"))


@plugin_tool()
async def get_price(
    ids: str,
    vs_currencies: str = "usd",
    include_market_cap: bool = True,
    include_24hr_vol: bool = True,
    include_24hr_change: bool = True,
) -> dict:
    """Get current price for coins.

    Args:
        ids: Comma-separated coin IDs (e.g., "bitcoin,ethereum")
        vs_currencies: Target currencies (e.g., "usd")
        include_market_cap: Include market cap data
        include_24hr_vol: Include 24h volume data
        include_24hr_change: Include 24h change data
    """
    client = _client()
    try:
        return client.get_price(
            ids, vs_currencies, include_market_cap, include_24hr_vol, include_24hr_change
        )
    finally:
        client.close()


@plugin_tool()
async def get_markets(
    vs_currency: str = "usd",
    order: str = "market_cap_desc",
    per_page: int = 100,
    page: int = 1,
) -> list[dict]:
    """List coins by market cap.

    Args:
        vs_currency: Target currency
        order: Sort order
        per_page: Results per page
        page: Page number
    """
    client = _client()
    try:
        return client.get_markets(vs_currency=vs_currency, order=order, per_page=per_page, page=page)
    finally:
        client.close()


@plugin_tool()
async def get_coin(coin_id: str) -> dict:
    """Get detailed coin information.

    Args:
        coin_id: Coin ID (e.g., "bitcoin", "ethereum")
    """
    client = _client()
    try:
        return client.get_coin(coin_id)
    finally:
        client.close()


@plugin_tool()
async def get_trending() -> dict:
    """Get trending coins on CoinGecko."""
    client = _client()
    try:
        return client.get_trending()
    finally:
        client.close()


@plugin_tool()
async def search(query: str) -> dict:
    """Search for coins by name or symbol.

    Args:
        query: Search query string
    """
    client = _client()
    try:
        return client.search(query)
    finally:
        client.close()


@plugin_tool()
async def get_market_chart(
    coin_id: str,
    vs_currency: str = "usd",
    days: int = 30,
) -> dict:
    """Get historical market data for a coin.

    Args:
        coin_id: Coin ID (e.g., "bitcoin")
        vs_currency: Target currency
        days: Number of days of history
    """
    client = _client()
    try:
        return client.get_market_chart(coin_id, vs_currency=vs_currency, days=days)
    finally:
        client.close()


@plugin_tool()
async def get_categories() -> list[dict]:
    """List all coin categories with market data."""
    client = _client()
    try:
        return client.get_categories()
    finally:
        client.close()


@plugin_tool()
async def get_exchanges(per_page: int = 100, page: int = 1) -> list[dict]:
    """List exchanges by trading volume.

    Args:
        per_page: Results per page
        page: Page number
    """
    client = _client()
    try:
        return client.get_exchanges(per_page=per_page, page=page)
    finally:
        client.close()
