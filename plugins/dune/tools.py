"""Dune plugin tools — works both as imported plugin and standalone."""

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

from . import client


def _ensure_key() -> None:
    """Set DUNE_API_KEY env var from secret() so the client module picks it up."""
    os.environ.setdefault("DUNE_API_KEY", secret("DUNE_API_KEY"))


@plugin_tool()
async def execute_query(query_id: int, params: dict[str, Any] | None = None) -> dict:
    """Execute a Dune query and return the execution ID.

    Args:
        query_id: The Dune query ID
        params: Optional query parameters
    """
    _ensure_key()
    return client.execute_query(query_id, params)


@plugin_tool()
async def get_execution_status(execution_id: str) -> dict:
    """Get the status of a Dune query execution.

    Args:
        execution_id: The execution ID
    """
    _ensure_key()
    return client.get_execution_status(execution_id)


@plugin_tool()
async def get_execution_results(execution_id: str) -> dict:
    """Get the results of a completed Dune execution.

    Args:
        execution_id: The execution ID
    """
    _ensure_key()
    return client.get_execution_results(execution_id)


@plugin_tool()
async def cancel_execution(execution_id: str) -> dict:
    """Cancel a running Dune execution.

    Args:
        execution_id: The execution ID
    """
    _ensure_key()
    return client.cancel_execution(execution_id)


@plugin_tool()
async def get_query(query_id: int) -> dict:
    """Get Dune query metadata.

    Args:
        query_id: The Dune query ID
    """
    _ensure_key()
    return client.get_query(query_id)
