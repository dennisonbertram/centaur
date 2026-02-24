"""Messari API client."""

import os
from typing import Any

import httpx

BASE_URL_V1 = "https://data.messari.io/api/v1"
BASE_URL_V2 = "https://data.messari.io/api/v2"


def get_client() -> httpx.Client:
    """Get authenticated Messari HTTP client."""
    api_key = os.getenv("MESSARI_API_KEY")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-messari-api-key"] = api_key
    return httpx.Client(headers=headers, timeout=30.0)


def _request(endpoint: str, version: int = 1, params: dict | None = None) -> dict[str, Any]:
    """Make request to Messari API."""
    base_url = BASE_URL_V1 if version == 1 else BASE_URL_V2
    url = f"{base_url}{endpoint}"
    with get_client() as client:
        response = client.get(url, params=params)
        if response.status_code >= 400:
            try:
                error = response.json()
                msg = error.get("status", {}).get("error_message", response.text)
            except Exception:
                msg = response.text
            raise RuntimeError(f"Messari API error ({response.status_code}): {msg}")
        return response.json()


def list_assets(limit: int = 20, fields: str | None = None) -> list[dict]:
    """List all assets."""
    params: dict[str, Any] = {"limit": limit}
    if fields:
        params["fields"] = fields
    data = _request("/assets", version=1, params=params)
    return data.get("data", [])


def get_asset(asset_key: str) -> dict:
    """Get asset by slug or ID."""
    data = _request(f"/assets/{asset_key}", version=1)
    return data.get("data", {})


def get_asset_metrics(asset_key: str) -> dict:
    """Get metrics for an asset."""
    data = _request(f"/assets/{asset_key}/metrics", version=1)
    return data.get("data", {})


def get_asset_profile(asset_key: str) -> dict:
    """Get profile for an asset (v2)."""
    data = _request(f"/assets/{asset_key}/profile", version=2)
    return data.get("data", {})


def get_asset_markets(asset_key: str) -> list[dict]:
    """Get markets for an asset."""
    data = _request(f"/assets/{asset_key}/markets", version=1)
    return data.get("data", [])


def get_news(limit: int = 10) -> list[dict]:
    """Get latest news."""
    params = {"limit": limit}
    data = _request("/news", version=1, params=params)
    return data.get("data", [])


def get_timeseries(
    asset_key: str,
    metric: str,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Get timeseries data for an asset metric."""
    params: dict[str, Any] = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    data = _request(f"/assets/{asset_key}/metrics/{metric}/time-series", version=1, params=params)
    return data.get("data", {})


def raw_request(endpoint: str, version: int = 1, params: dict | None = None) -> dict:
    """Make a raw API call to any endpoint."""
    return _request(endpoint, version=version, params=params)
