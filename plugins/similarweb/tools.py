"""SimilarWeb plugin tools — works both as imported plugin and standalone."""
from __future__ import annotations

import os
from datetime import date, timedelta
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

from .client import SimilarWebClient


def _client() -> SimilarWebClient:
    return SimilarWebClient(api_key=secret("SIMILARWEB_API_KEY"))


def _default_dates() -> tuple[date, date]:
    end = date.today().replace(day=1) - timedelta(days=1)
    start = (end - timedelta(days=90)).replace(day=1)
    return start, end


@plugin_tool(name="similarweb_traffic")
def traffic(domain: str, country: str = "world") -> dict:
    """Get website traffic visits for a domain (last 3 months).

    Args:
        domain: Website domain (e.g., 'google.com')
        country: Country code or 'world'
    """
    start, end = _default_dates()
    return _client().get_visits(domain, start, end, country=country)


@plugin_tool(name="similarweb_rank")
def rank(domain: str) -> dict:
    """Get global and industry rank for a domain.

    Args:
        domain: Website domain
    """
    c = _client()
    return {
        "global_rank": c.get_global_rank(domain),
        "industry_rank": c.get_industry_rank(domain),
    }


@plugin_tool(name="similarweb_sources")
def sources(domain: str, country: str = "world") -> dict:
    """Get traffic sources breakdown by channel.

    Args:
        domain: Website domain
        country: Country code or 'world'
    """
    start, end = _default_dates()
    return _client().get_traffic_sources(domain, start, end, country=country)


@plugin_tool(name="similarweb_geography")
def geography(domain: str) -> dict:
    """Get traffic geography distribution by country.

    Args:
        domain: Website domain
    """
    start, end = _default_dates()
    return _client().get_geography(domain, start, end)


@plugin_tool(name="similarweb_similar_sites")
def similar_sites(domain: str) -> dict:
    """Get similar/competitor websites.

    Args:
        domain: Website domain
    """
    return _client().get_similar_sites(domain)


@plugin_tool(name="similarweb_keywords")
def keywords(domain: str, country: str = "world", limit: int = 50) -> dict:
    """Get search keywords driving traffic to a domain.

    Args:
        domain: Website domain
        country: Country code or 'world'
        limit: Max results
    """
    start, end = _default_dates()
    return _client().get_keywords(domain, start, end, country=country, limit=limit)
