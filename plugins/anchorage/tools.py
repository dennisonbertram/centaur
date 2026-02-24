"""Anchorage plugin tools — works both as imported plugin and standalone."""

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

from .client import AnchorageClient


def _client(fund: str = "pf") -> AnchorageClient:
    return AnchorageClient(fund=fund)


@plugin_tool()
def list_vaults(fund: str = "pf", limit: int = 25) -> list[dict]:
    """List Anchorage vaults.

    Args:
        fund: Fund - 'pf' (Paradigm Fund), 'p1' (Paradigm One), 'p2' (Paradigm Two)
        limit: Max results
    """
    return _client(fund).list_vaults(limit=limit)


@plugin_tool()
def get_balances(fund: str = "pf") -> list[dict]:
    """Get all Anchorage balances across vaults.

    Args:
        fund: Fund - 'pf', 'p1', or 'p2'
    """
    return _client(fund).get_balances()


@plugin_tool()
def get_vault_balance(vault_id: str, fund: str = "pf") -> list[dict]:
    """Get balance for a specific Anchorage vault.

    Args:
        vault_id: Vault ID
        fund: Fund - 'pf', 'p1', or 'p2'
    """
    return _client(fund).get_vault_balance(vault_id)


@plugin_tool()
def list_transactions(fund: str = "pf", limit: int = 50, vault_id: str = "") -> list[dict]:
    """List Anchorage transfers.

    Args:
        fund: Fund - 'pf', 'p1', or 'p2'
        limit: Max results
        vault_id: Filter by vault ID (optional)
    """
    return _client(fund).list_transactions(limit=limit, vault_id=vault_id or None)


@plugin_tool()
def list_staking_delegations(fund: str = "pf", limit: int = 50) -> list[dict]:
    """List Anchorage staking delegations.

    Args:
        fund: Fund - 'pf', 'p1', or 'p2'
        limit: Max results
    """
    return _client(fund).list_staking_delegations(limit=limit)


@plugin_tool()
def get_staking_summary(fund: str = "pf") -> dict:
    """Get Anchorage staking summary across all assets.

    Args:
        fund: Fund - 'pf', 'p1', or 'p2'
    """
    return _client(fund).get_staking_summary()


@plugin_tool()
def list_staking_rewards(fund: str = "pf", limit: int = 50) -> list[dict]:
    """List Anchorage staking rewards.

    Args:
        fund: Fund - 'pf', 'p1', or 'p2'
        limit: Max results
    """
    return _client(fund).list_staking_rewards(limit=limit)


@plugin_tool()
def list_validators(fund: str = "pf", asset: str = "") -> list[dict]:
    """List available Anchorage validators for staking.

    Args:
        fund: Fund - 'pf', 'p1', or 'p2'
        asset: Filter by asset type (e.g., ETH, SOL) — optional
    """
    return _client(fund).list_validators(asset=asset or None)
