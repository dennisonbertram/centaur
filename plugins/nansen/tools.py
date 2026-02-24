"""Nansen plugin tools — works both as imported plugin and standalone."""
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

from .client import NansenClient


def _client() -> NansenClient:
    return NansenClient(api_key=secret("NANSEN_API_KEY"))


@plugin_tool(name="nansen_address_labels")
def address_labels(address: str, chain: str = "ethereum") -> dict:
    """Get Nansen labels for a wallet address.

    Args:
        address: Wallet address to lookup
        chain: Blockchain (ethereum, solana, base, etc.)
    """
    return _client().get_address_labels(address, chain=chain)


@plugin_tool(name="nansen_address_balance")
def address_balance(
    address: str | None = None,
    entity_name: str | None = None,
    chain: str = "ethereum",
    limit: int = 20,
) -> dict:
    """Get current token balances for an address or entity.

    Args:
        address: Wallet address
        entity_name: Entity name (e.g., 'Vitalik Buterin')
        chain: Blockchain
        limit: Max results
    """
    return _client().get_address_balance(
        address=address, entity_name=entity_name, chain=chain, per_page=limit
    )


@plugin_tool(name="nansen_smart_money_holdings")
def smart_money_holdings(
    chains: list[str] | None = None,
    labels: list[str] | None = None,
    limit: int = 20,
) -> dict:
    """Get Smart Money token holdings.

    Args:
        chains: Filter by chains (e.g., ['ethereum', 'base'])
        labels: Filter by labels (e.g., ['Fund', 'Smart Trader'])
        limit: Max results
    """
    return _client().get_smart_money_holdings(
        chains=chains, labels=labels, per_page=limit
    )


@plugin_tool(name="nansen_smart_money_netflows")
def smart_money_netflows(
    chains: list[str] | None = None,
    labels: list[str] | None = None,
    limit: int = 20,
) -> dict:
    """Get Smart Money net flows — what smart money is buying/selling.

    Args:
        chains: Filter by chains
        labels: Filter by labels
        limit: Max results
    """
    return _client().get_smart_money_netflows(
        chains=chains, labels=labels, per_page=limit
    )


@plugin_tool(name="nansen_token_holders")
def token_holders(token_address: str, chain: str = "ethereum", limit: int = 20) -> dict:
    """Get top holders for a token.

    Args:
        token_address: Token contract address
        chain: Blockchain
        limit: Max results
    """
    return _client().get_token_holders(token_address, chain=chain, per_page=limit)


@plugin_tool(name="nansen_token_flows")
def token_flows(token_address: str, chain: str = "ethereum") -> dict:
    """Get token inflows/outflows by entity type.

    Args:
        token_address: Token contract address
        chain: Blockchain
    """
    return _client().get_token_flows(token_address, chain=chain)


@plugin_tool(name="nansen_entity_search")
def entity_search(query: str, limit: int = 20) -> dict:
    """Search for an entity by name.

    Args:
        query: Search query
        limit: Max results
    """
    return _client().search_entity(query, per_page=limit)
