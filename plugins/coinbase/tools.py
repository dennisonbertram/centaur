"""Coinbase plugin tools — works both as imported plugin and standalone."""

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

from .client import (
    get_portfolio_balances,
    get_staking_rewards,
    list_activities,
    list_assets,
    list_portfolios,
    list_staking_positions,
    list_transactions,
    list_wallets,
)


@plugin_tool()
def portfolios() -> list[dict]:
    """List all Coinbase Prime portfolios."""
    return list_portfolios()


@plugin_tool()
def balances(portfolio_id: str, symbols: str = "") -> list[dict]:
    """Get Coinbase Prime portfolio balances.

    Args:
        portfolio_id: Portfolio ID
        symbols: Comma-separated symbols to filter (optional)
    """
    symbol_list = symbols.split(",") if symbols else None
    return get_portfolio_balances(portfolio_id, symbol_list)


@plugin_tool()
def wallets(portfolio_id: str, wallet_type: str = "") -> list[dict]:
    """List wallets for a Coinbase Prime portfolio.

    Args:
        portfolio_id: Portfolio ID
        wallet_type: Filter by type (VAULT, TRADING) — optional
    """
    return list_wallets(portfolio_id, wallet_type or None)


@plugin_tool()
def transactions(
    portfolio_id: str, symbols: str = "", types: str = "", limit: int = 25
) -> list[dict]:
    """List Coinbase Prime transactions.

    Args:
        portfolio_id: Portfolio ID
        symbols: Comma-separated symbols to filter (optional)
        types: Comma-separated types to filter (optional)
        limit: Max results
    """
    symbol_list = symbols.split(",") if symbols else None
    type_list = types.split(",") if types else None
    return list_transactions(portfolio_id, symbol_list, type_list, limit)


@plugin_tool()
def staking_positions(portfolio_id: str) -> list[dict]:
    """List staking positions for a Coinbase Prime portfolio.

    Args:
        portfolio_id: Portfolio ID
    """
    return list_staking_positions(portfolio_id)


@plugin_tool()
def staking_rewards(
    portfolio_id: str, symbol: str = "", start_date: str = "", end_date: str = ""
) -> list[dict]:
    """Get staking rewards for a Coinbase Prime portfolio.

    Args:
        portfolio_id: Portfolio ID
        symbol: Filter by symbol (optional)
        start_date: Start date YYYY-MM-DD (optional)
        end_date: End date YYYY-MM-DD (optional)
    """
    return get_staking_rewards(
        portfolio_id, symbol or None, start_date or None, end_date or None
    )


@plugin_tool()
def activities(portfolio_id: str, symbols: str = "", categories: str = "", limit: int = 25) -> list[dict]:
    """List activities for a Coinbase Prime portfolio.

    Args:
        portfolio_id: Portfolio ID
        symbols: Comma-separated symbols to filter (optional)
        categories: Comma-separated categories to filter (optional)
        limit: Max results
    """
    symbol_list = symbols.split(",") if symbols else None
    category_list = categories.split(",") if categories else None
    return list_activities(portfolio_id, symbol_list, category_list, limit)


@plugin_tool()
def assets() -> list[dict]:
    """List supported Coinbase Prime assets."""
    return list_assets()
