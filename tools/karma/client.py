"""Karma API client."""

import httpx


class KarmaClient:
    """Client for Karma DAO governance analytics API.

    Provides access to DAO delegate reputation scores, contributor data,
    and governance participation metrics. No API key required for public endpoints.
    """

    def __init__(self, timeout: float = 30.0):
        self.base_url = "https://api.karmahq.xyz/api"
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _request(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Make an API request."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", data) if isinstance(data, dict) else data
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Request failed: {e}")

    def list_daos(self) -> list[dict]:
        """List all supported DAOs.

        Returns:
            List of DAO data
        """
        return self._request("/daos")

    def get_delegates(
        self,
        dao_name: str,
        limit: int = 20,
        offset: int = 0,
        order_by: str = "score",
    ) -> list[dict]:
        """Get delegates for a DAO.

        Args:
            dao_name: DAO name (e.g., "aave", "uniswap", "optimism")
            limit: Maximum number of delegates to return
            offset: Offset for pagination
            order_by: Sort field (e.g., "score", "delegatedVotes")

        Returns:
            List of delegate dicts
        """
        return self._request(
            f"/dao/{dao_name}/delegates",
            params={"pageSize": limit, "offset": offset, "order": order_by},
        )

    def get_delegate(self, dao_name: str, address: str) -> dict:
        """Get a specific delegate's profile and stats.

        Args:
            dao_name: DAO name (e.g., "aave", "uniswap")
            address: Delegate's Ethereum address

        Returns:
            Delegate profile dict
        """
        return self._request(f"/dao/{dao_name}/delegates/{address}")

    def get_delegate_activity(self, dao_name: str, address: str) -> list[dict]:
        """Get voting and proposal activity for a delegate.

        Args:
            dao_name: DAO name
            address: Delegate's Ethereum address

        Returns:
            List of activity entries
        """
        return self._request(f"/dao/{dao_name}/delegates/{address}/activity")

    def get_dao_stats(self, dao_name: str) -> dict:
        """Get governance statistics for a DAO.

        Args:
            dao_name: DAO name (e.g., "aave", "uniswap")

        Returns:
            DAO governance stats
        """
        return self._request(f"/dao/{dao_name}/stats")

    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _client() -> KarmaClient:
    return KarmaClient()
