"""BitGo API client."""

import os
from typing import Any

import httpx

BASE_URL = "https://app.bitgo.com/api/v2"


def get_client() -> httpx.Client:
    """Get authenticated BitGo HTTP client."""
    token = os.getenv("BITGO_API_KEY")
    if not token:
        raise RuntimeError(
            "BITGO_API_KEY not set.\n"
            "Generate one at https://app.bitgo.com/settings/developer-options"
        )
    return httpx.Client(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _request(method: str, path: str, **kwargs) -> dict[str, Any]:
    """Make authenticated request to BitGo API."""
    with get_client() as client:
        response = client.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                error = response.json()
                msg = error.get("error", error.get("message", response.text))
            except Exception:
                msg = response.text
            raise RuntimeError(f"BitGo API error ({response.status_code}): {msg}")
        return response.json()


def list_wallets(coin: str | None = None, limit: int = 25) -> list[dict]:
    """List all wallets or wallets for a specific coin."""
    params: dict[str, Any] = {"limit": limit}
    if coin:
        data = _request("GET", f"/{coin}/wallet", params=params)
    else:
        data = _request("GET", "/wallets", params=params)
    return data.get("wallets", [])


def get_wallet(coin: str, wallet_id: str) -> dict:
    """Get wallet details by coin and ID."""
    data = _request("GET", f"/{coin}/wallet/{wallet_id}")
    return data


def get_wallet_balance(coin: str, wallet_id: str) -> dict:
    """Get wallet balance."""
    data = _request("GET", f"/{coin}/wallet/{wallet_id}")
    return {
        "coin": data.get("coin"),
        "label": data.get("label"),
        "balance": data.get("balance"),
        "balanceString": data.get("balanceString"),
        "confirmedBalance": data.get("confirmedBalance"),
        "confirmedBalanceString": data.get("confirmedBalanceString"),
        "spendableBalance": data.get("spendableBalance"),
        "spendableBalanceString": data.get("spendableBalanceString"),
    }


def get_total_balances(enterprise_id: str | None = None) -> dict:
    """Get total balances across all wallets."""
    params = {}
    if enterprise_id:
        params["enterprise"] = enterprise_id
    data = _request("GET", "/wallet/balances", params=params if params else None)
    return data


def list_transactions(
    coin: str, wallet_id: str, limit: int = 25, prev_id: str | None = None
) -> list[dict]:
    """List transactions (transfers) for a wallet."""
    params: dict[str, Any] = {"limit": limit}
    if prev_id:
        params["prevId"] = prev_id
    data = _request("GET", f"/{coin}/wallet/{wallet_id}/transfer", params=params)
    return data.get("transfers", [])


def get_transaction(coin: str, wallet_id: str, transfer_id: str) -> dict:
    """Get transaction details."""
    data = _request("GET", f"/{coin}/wallet/{wallet_id}/transfer/{transfer_id}")
    return data


def list_addresses(coin: str, wallet_id: str, limit: int = 25) -> list[dict]:
    """List addresses for a wallet."""
    params: dict[str, Any] = {"limit": limit}
    data = _request("GET", f"/{coin}/wallet/{wallet_id}/addresses", params=params)
    return data.get("addresses", [])


def list_enterprises() -> list[dict]:
    """List enterprises the user belongs to."""
    data = _request("GET", "/enterprise")
    return data.get("enterprises", [])


def get_enterprise(enterprise_id: str) -> dict:
    """Get enterprise details."""
    data = _request("GET", f"/enterprise/{enterprise_id}")
    return data


def raw_request(endpoint: str, method: str = "GET", **kwargs) -> dict | list:
    """Make a raw API call to any endpoint."""
    return _request(method, endpoint, **kwargs)


# Staking endpoints
def list_staking_coins() -> list[dict]:
    """List coins available for staking."""
    data = _request("GET", "/staking/v1/coins")
    return data.get("coins", []) if isinstance(data, dict) else data


def list_staking_requests(enterprise_id: str | None = None, limit: int = 25) -> list[dict]:
    """List staking requests for an enterprise."""
    params: dict[str, Any] = {"limit": limit}
    if enterprise_id:
        data = _request("GET", f"/staking/v1/enterprises/{enterprise_id}/requests", params=params)
    else:
        data = _request("GET", "/staking/v1/requests", params=params)
    return data.get("requests", []) if isinstance(data, dict) else data


def get_staking_request(request_id: str) -> dict:
    """Get details of a staking request."""
    data = _request("GET", f"/staking/v1/requests/{request_id}")
    return data


def list_staking_delegations(coin: str, wallet_id: str, limit: int = 25) -> list[dict]:
    """List staking delegations for a wallet."""
    params: dict[str, Any] = {"limit": limit}
    data = _request("GET", f"/{coin}/wallet/{wallet_id}/staking/delegations", params=params)
    return data.get("delegations", []) if isinstance(data, dict) else data


def list_staking_rewards(enterprise_id: str) -> list[dict]:
    """List staking rewards for an enterprise."""
    data = _request("GET", f"/staking/v1/enterprises/{enterprise_id}/rewards")
    return data.get("rewards", []) if isinstance(data, dict) else data


def get_staking_wallet_attributes(coin: str, wallet_id: str) -> dict:
    """Get staking attributes for a wallet."""
    data = _request("GET", f"/{coin}/wallet/{wallet_id}/staking/attributes")
    return data


def list_partnered_validators(coin: str | None = None) -> list[dict]:
    """List partnered validators for staking."""
    params = {}
    if coin:
        params["coin"] = coin
    data = _request("GET", "/staking/v1/validators", params=params if params else None)
    return data.get("validators", []) if isinstance(data, dict) else data
