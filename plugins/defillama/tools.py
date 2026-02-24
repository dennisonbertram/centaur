"""DefiLlama plugin tools — works both as imported plugin and standalone."""

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

from .client import DefiLlamaClient


def _client() -> DefiLlamaClient:
    return DefiLlamaClient(api_key=secret("DEFILLAMA_API_KEY", default=None))


@plugin_tool()
async def list_stablecoins() -> list[dict]:
    """List all stablecoins with their market caps."""
    return _client().list_stablecoins()


@plugin_tool()
async def get_stablecoin(asset_id: str) -> dict:
    """Get details for a specific stablecoin including chain breakdown.

    Args:
        asset_id: The stablecoin ID (e.g., "1" for USDT)
    """
    return _client().get_stablecoin(asset_id)


@plugin_tool()
async def get_stablecoin_charts(chain: str | None = None) -> list[dict]:
    """Get historical stablecoin market cap data.

    Args:
        chain: Optional chain name to filter (e.g., "ethereum", "arbitrum")
    """
    return _client().get_stablecoin_charts(chain)


@plugin_tool()
async def list_protocols(limit: int = 50) -> list[dict]:
    """List DeFi protocols by TVL.

    Args:
        limit: Max number of protocols to return
    """
    data = _client().list_protocols()
    return sorted(data, key=lambda x: x.get("tvl") or 0, reverse=True)[:limit]


@plugin_tool()
async def get_protocol(slug: str) -> dict:
    """Get detailed protocol information including historical TVL.

    Args:
        slug: Protocol slug (e.g., "aave", "uniswap")
    """
    return _client().get_protocol(slug)


@plugin_tool()
async def get_tvl(protocol: str) -> float:
    """Get current TVL for a protocol.

    Args:
        protocol: Protocol slug
    """
    return _client().get_tvl(protocol)


@plugin_tool()
async def list_chains(limit: int = 50) -> list[dict]:
    """List all chains by TVL.

    Args:
        limit: Max number of chains to return
    """
    data = _client().list_chains()
    return sorted(data, key=lambda x: x.get("tvl") or 0, reverse=True)[:limit]


@plugin_tool()
async def get_dex_volumes(chain: str | None = None) -> dict:
    """Get DEX trading volumes.

    Args:
        chain: Optional chain name to filter
    """
    return _client().get_dex_volumes(chain)


@plugin_tool()
async def list_bridges(limit: int = 50) -> list[dict]:
    """List all bridges sorted by daily volume.

    Args:
        limit: Max number of bridges to return
    """
    data = _client().list_bridges()
    return sorted(data, key=lambda x: x.get("lastDailyVolume", 0) or 0, reverse=True)[:limit]


@plugin_tool()
async def get_fees(chain: str | None = None) -> dict:
    """Get protocol fees overview.

    Args:
        chain: Optional chain name to filter
    """
    return _client().get_fees(chain)


@plugin_tool()
async def get_protocol_fees(protocol: str) -> dict:
    """Get fees for a specific protocol.

    Args:
        protocol: Protocol slug
    """
    return _client().get_protocol_fees(protocol)
