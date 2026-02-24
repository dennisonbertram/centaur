"""FalconX plugin tools — works both as imported plugin and standalone."""

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

from .client import FalconXClient


def _client(account: str = "p1") -> FalconXClient:
    return FalconXClient(account=account)


@plugin_tool()
def get_balances(account: str = "p1") -> dict:
    """Get FalconX account balances.

    Args:
        account: Account type - 'p1' (Paradigm One) or 'pf' (Paradigm Fund)
    """
    return _client(account).get_balances()


@plugin_tool()
def get_quote(
    base: str, quote: str, quantity: float, side: str = "buy", account: str = "p1"
) -> dict:
    """Get a FalconX quote for a trade.

    Args:
        base: Base token (e.g., BTC)
        quote: Quote token (e.g., USD)
        quantity: Amount to trade
        side: Trade side - 'buy' or 'sell'
        account: Account type - 'p1' or 'pf'
    """
    return _client(account).get_quote(base, quote, quantity, side)


@plugin_tool()
def execute_quote(quote_id: str, account: str = "p1") -> dict:
    """Execute a previously obtained FalconX quote.

    Args:
        quote_id: The FalconX quote ID to execute
        account: Account type - 'p1' or 'pf'
    """
    return _client(account).execute_quote(quote_id)


@plugin_tool()
def list_trades(days: int = 30, account: str = "p1") -> list:
    """List FalconX trade history.

    Args:
        days: Number of days of history (max 31)
        account: Account type - 'p1' or 'pf'
    """
    return _client(account).list_trades(days=days)


@plugin_tool()
def get_trade(trade_id: str, account: str = "p1") -> dict:
    """Get details for a specific FalconX trade.

    Args:
        trade_id: The FalconX quote/trade ID
        account: Account type - 'p1' or 'pf'
    """
    return _client(account).get_trade(trade_id)


@plugin_tool()
def list_pairs(account: str = "p1") -> list:
    """List available FalconX trading pairs.

    Args:
        account: Account type - 'p1' or 'pf'
    """
    return _client(account).list_pairs()
