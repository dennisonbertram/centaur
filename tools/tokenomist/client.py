"""Tokenomist API client."""

import os

import httpx


class TokenomistClient:
    """Client for Tokenomist API.

    Provides access to token unlock schedules, vesting, emissions, and allocations.
    Requires an API key set via TOKENOMIST_API_KEY environment variable.
    """

    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        self._api_key = api_key or os.getenv("TOKENOMIST_API_KEY")
        if not self._api_key:
            raise RuntimeError("TOKENOMIST_API_KEY not set.")
        self.base_url = "https://api.tokenomist.ai/v1"
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _request(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Make an API request."""
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self._api_key}",
        }
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Request failed: {e}")

    def list_tokens(self, limit: int = 50) -> list[dict]:
        """List available tokens.

        Args:
            limit: Maximum number of tokens to return

        Returns:
            List of tokens with id, name, symbol
        """
        return self._request("/token/list", params={"limit": limit})

    def get_allocations(self, token_id: str) -> list[dict]:
        """Get token allocation breakdown.

        Args:
            token_id: The token identifier

        Returns:
            List of allocation entries
        """
        return self._request(f"/token/{token_id}/allocations")

    def get_unlock_events(self, token_id: str) -> list[dict]:
        """Get scheduled unlock events with timestamps.

        Args:
            token_id: The token identifier

        Returns:
            List of unlock events
        """
        return self._request(f"/token/{token_id}/unlocks")

    def get_daily_emissions(self, token_id: str) -> list[dict]:
        """Get daily emission data.

        Args:
            token_id: The token identifier

        Returns:
            List of daily emission entries
        """
        return self._request(f"/token/{token_id}/emissions")

    def get_fundraising(self, token_id: str) -> list[dict]:
        """Get fundraising rounds and investors.

        Args:
            token_id: The token identifier

        Returns:
            List of fundraising rounds
        """
        return self._request(f"/token/{token_id}/fundraising")

    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _client() -> TokenomistClient:
    return TokenomistClient()
