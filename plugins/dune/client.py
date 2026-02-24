"""Dune Analytics API client."""

import os
from typing import Any

import httpx

BASE_URL = "https://api.dune.com/api/v1"


def _get_api_key() -> str:
    """Get Dune API key from environment."""
    api_key = os.getenv("DUNE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DUNE_API_KEY not set.\nGet your API key at https://dune.com/settings/api"
        )
    return api_key


def get_client() -> httpx.Client:
    """Get authenticated Dune HTTP client."""
    return httpx.Client(
        base_url=BASE_URL,
        headers={
            "X-Dune-API-Key": _get_api_key(),
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )


def _request(method: str, path: str, **kwargs) -> dict[str, Any]:
    """Make authenticated request to Dune API."""
    with get_client() as client:
        response = client.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                error = response.json()
                msg = error.get("error", response.text)
            except Exception:
                msg = response.text
            raise RuntimeError(f"Dune API error ({response.status_code}): {msg}")
        return response.json()


def execute_query(query_id: int, params: dict[str, Any] | None = None) -> dict:
    """Execute a query and return execution ID.

    Args:
        query_id: The Dune query ID
        params: Optional query parameters

    Returns:
        Dict with execution_id and state
    """
    body = {}
    if params:
        body["query_parameters"] = params
    return _request("POST", f"/query/{query_id}/execute", json=body if body else None)


def get_execution_status(execution_id: str) -> dict:
    """Get the status of a query execution.

    Args:
        execution_id: The execution ID

    Returns:
        Dict with state, queue position, etc.
    """
    return _request("GET", f"/execution/{execution_id}/status")


def get_execution_results(execution_id: str) -> dict:
    """Get the results of a completed execution.

    Args:
        execution_id: The execution ID

    Returns:
        Dict with result rows and metadata
    """
    return _request("GET", f"/execution/{execution_id}/results")


def cancel_execution(execution_id: str) -> dict:
    """Cancel a running execution.

    Args:
        execution_id: The execution ID

    Returns:
        Cancellation confirmation
    """
    return _request("POST", f"/execution/{execution_id}/cancel")


def get_query(query_id: int) -> dict:
    """Get query metadata.

    Args:
        query_id: The Dune query ID

    Returns:
        Query metadata including name, description, parameters
    """
    return _request("GET", f"/query/{query_id}")


def raw_request(method: str, endpoint: str, **kwargs) -> dict:
    """Make a raw API call.

    Args:
        method: HTTP method
        endpoint: API endpoint path

    Returns:
        JSON response
    """
    return _request(method, endpoint, **kwargs)
