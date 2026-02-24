"""BitGo plugin tools — works both as imported plugin and standalone."""

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
    get_total_balances,
    get_wallet_balance,
    list_enterprises,
    list_staking_coins,
    list_staking_requests,
    list_staking_rewards,
    list_transactions,
    list_wallets,
    list_partnered_validators,
)


@plugin_tool()
def wallets(coin: str = "", limit: int = 25) -> list[dict]:
    """List BitGo wallets.

    Args:
        coin: Filter by coin (e.g., btc, eth) — optional
        limit: Max results
    """
    return list_wallets(coin=coin or None, limit=limit)


@plugin_tool()
def wallet_balance(coin: str, wallet_id: str) -> dict:
    """Get BitGo wallet balance.

    Args:
        coin: Coin type (e.g., btc, eth)
        wallet_id: Wallet ID
    """
    return get_wallet_balance(coin, wallet_id)


@plugin_tool()
def total_balances(enterprise_id: str = "") -> dict:
    """Get total BitGo balances across all wallets.

    Args:
        enterprise_id: Enterprise ID (optional)
    """
    return get_total_balances(enterprise_id=enterprise_id or None)


@plugin_tool()
def transactions(coin: str, wallet_id: str, limit: int = 25) -> list[dict]:
    """List BitGo transactions for a wallet.

    Args:
        coin: Coin type (e.g., btc, eth)
        wallet_id: Wallet ID
        limit: Max results
    """
    return list_transactions(coin, wallet_id, limit=limit)


@plugin_tool()
def enterprises() -> list[dict]:
    """List BitGo enterprises."""
    return list_enterprises()


@plugin_tool()
def staking_coins() -> list[dict]:
    """List BitGo coins available for staking."""
    return list_staking_coins()


@plugin_tool()
def staking_requests(enterprise_id: str = "", limit: int = 25) -> list[dict]:
    """List BitGo staking requests.

    Args:
        enterprise_id: Enterprise ID (optional)
        limit: Max results
    """
    return list_staking_requests(enterprise_id=enterprise_id or None, limit=limit)


@plugin_tool()
def staking_rewards(enterprise_id: str) -> list[dict]:
    """List BitGo staking rewards for an enterprise.

    Args:
        enterprise_id: Enterprise ID
    """
    return list_staking_rewards(enterprise_id)


@plugin_tool()
def validators(coin: str = "") -> list[dict]:
    """List BitGo partnered validators for staking.

    Args:
        coin: Filter by coin (optional)
    """
    return list_partnered_validators(coin=coin or None)
