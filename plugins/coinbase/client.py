"""Coinbase Prime API client with HMAC authentication."""

import base64
import hashlib
import hmac
import os
import time
from typing import Any

import httpx

BASE_URL = "https://api.prime.coinbase.com/v1"


def get_credentials() -> tuple[str, str, str, str]:
    """Get Coinbase Prime API credentials from environment."""
    api_key = os.getenv("COINBASE_API_KEY")
    api_secret = os.getenv("COINBASE_API_SECRET")
    passphrase = os.getenv("COINBASE_API_PASSPHRASE")
    portfolio_id = os.getenv("COINBASE_PORTFOLIO_ID")

    if not api_key or not api_secret or not passphrase:
        raise RuntimeError(
            "Coinbase Prime credentials not set.\n"
            "Required: COINBASE_API_KEY, COINBASE_API_SECRET, COINBASE_API_PASSPHRASE\n"
            "Optional: COINBASE_PORTFOLIO_ID\n"
            "Generate keys at https://prime.coinbase.com -> Settings -> APIs"
        )
    return api_key, api_secret, passphrase, portfolio_id or ""


def sign_request(method: str, path: str, body: str, timestamp: str, secret: str) -> str:
    """Create HMAC signature for Coinbase Prime API."""
    message = f"{timestamp}{method}{path}{body}"
    signature = hmac.digest(secret.encode(), message.encode(), hashlib.sha256)
    return base64.b64encode(signature).decode()


def _request(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    """Make authenticated request to Coinbase Prime API."""
    api_key, api_secret, passphrase, _ = get_credentials()

    timestamp = str(int(time.time()))
    body_str = "" if body is None else str(body).replace("'", '"').replace(" ", "")

    # Signature must include /v1 prefix in path
    sign_path = f"/v1{path}"
    signature = sign_request(
        method, sign_path, body_str if method != "GET" else "", timestamp, api_secret
    )

    headers = {
        "X-CB-ACCESS-KEY": api_key,
        "X-CB-ACCESS-PASSPHRASE": passphrase,
        "X-CB-ACCESS-SIGNATURE": signature,
        "X-CB-ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json",
    }

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30.0) as client:
        if method == "GET":
            response = client.get(path)
        elif method == "POST":
            response = client.post(path, json=body)
        elif method == "DELETE":
            response = client.delete(path)
        else:
            response = client.request(method, path, json=body)

        if response.status_code >= 400:
            try:
                error = response.json()
                msg = error.get("message", error.get("error", response.text))
            except Exception:
                msg = response.text
            raise RuntimeError(f"Coinbase Prime API error ({response.status_code}): {msg}")
        return response.json()


def list_portfolios() -> list[dict]:
    """List all portfolios."""
    data = _request("GET", "/portfolios")
    return data.get("portfolios", [])


def get_portfolio(portfolio_id: str) -> dict:
    """Get portfolio details."""
    return _request("GET", f"/portfolios/{portfolio_id}")


def get_portfolio_balances(portfolio_id: str, symbols: list[str] | None = None) -> list[dict]:
    """Get portfolio balances."""
    path = f"/portfolios/{portfolio_id}/balances"
    if symbols:
        path += f"?symbols={','.join(symbols)}"
    data = _request("GET", path)
    return data.get("balances", [])


def list_wallets(portfolio_id: str, wallet_type: str | None = None) -> list[dict]:
    """List wallets for a portfolio."""
    path = f"/portfolios/{portfolio_id}/wallets"
    if wallet_type:
        path += f"?type={wallet_type}"
    data = _request("GET", path)
    return data.get("wallets", [])


def get_wallet(portfolio_id: str, wallet_id: str) -> dict:
    """Get wallet details."""
    return _request("GET", f"/portfolios/{portfolio_id}/wallets/{wallet_id}")


def get_wallet_balance(portfolio_id: str, wallet_id: str) -> dict:
    """Get wallet balance."""
    return _request("GET", f"/portfolios/{portfolio_id}/wallets/{wallet_id}/balance")


def list_transactions(
    portfolio_id: str,
    symbols: list[str] | None = None,
    types: list[str] | None = None,
    limit: int = 25,
) -> list[dict]:
    """List transactions for a portfolio."""
    path = f"/portfolios/{portfolio_id}/transactions?limit={limit}"
    if symbols:
        path += f"&symbols={','.join(symbols)}"
    if types:
        path += f"&types={','.join(types)}"
    data = _request("GET", path)
    return data.get("transactions", [])


def get_transaction(portfolio_id: str, transaction_id: str) -> dict:
    """Get transaction details."""
    return _request("GET", f"/portfolios/{portfolio_id}/transactions/{transaction_id}")


def list_activities(
    portfolio_id: str,
    symbols: list[str] | None = None,
    categories: list[str] | None = None,
    limit: int = 25,
) -> list[dict]:
    """List activities for a portfolio."""
    path = f"/portfolios/{portfolio_id}/activities?limit={limit}"
    if symbols:
        path += f"&symbols={','.join(symbols)}"
    if categories:
        path += f"&categories={','.join(categories)}"
    data = _request("GET", path)
    return data.get("activities", [])


def list_assets() -> list[dict]:
    """List supported assets."""
    data = _request("GET", "/assets")
    return data.get("assets", [])


def list_staking_positions(portfolio_id: str) -> list[dict]:
    """List staking positions for a portfolio."""
    data = _request("GET", f"/portfolios/{portfolio_id}/staking/positions")
    return data.get("positions", [])


def get_staking_rewards(
    portfolio_id: str,
    symbol: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Get staking rewards for a portfolio."""
    path = f"/portfolios/{portfolio_id}/staking/rewards"
    params = []
    if symbol:
        params.append(f"symbol={symbol}")
    if start_date:
        params.append(f"start_date={start_date}")
    if end_date:
        params.append(f"end_date={end_date}")
    if params:
        path += "?" + "&".join(params)
    data = _request("GET", path)
    return data.get("rewards", [])


def raw_request(endpoint: str, method: str = "GET", body: dict | None = None) -> dict | list:
    """Make a raw API call to any endpoint."""
    return _request(method, endpoint, body)
