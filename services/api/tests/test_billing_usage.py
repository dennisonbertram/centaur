from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from api.billing_usage import (
    assert_inference_credit_available,
    billing_events_configured,
    credit_check_configured,
    managed_inference_enabled,
    minimum_credit_cents,
)


def test_managed_inference_requires_explicit_enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CENTAUR_MANAGED_INFERENCE", raising=False)
    assert managed_inference_enabled() is False

    monkeypatch.setenv("CENTAUR_MANAGED_INFERENCE", "1")
    assert managed_inference_enabled() is True


def test_billing_events_require_url_secret_and_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CENTAUR_BILLING_EVENTS_URL", "https://dashboard.test/api/billing")
    monkeypatch.setenv("CENTAUR_BILLING_EVENTS_SECRET", "secret")
    monkeypatch.delenv("CENTAUR_DEPLOYMENT_ID", raising=False)
    assert billing_events_configured() is False

    monkeypatch.setenv("CENTAUR_DEPLOYMENT_ID", "demo")
    assert billing_events_configured() is True


def test_credit_check_requires_url_secret_and_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CENTAUR_CREDIT_CHECK_URL", "https://dashboard.test/api/check")
    monkeypatch.setenv("CENTAUR_BILLING_EVENTS_SECRET", "secret")
    monkeypatch.delenv("CENTAUR_DEPLOYMENT_ID", raising=False)
    assert credit_check_configured() is False

    monkeypatch.setenv("CENTAUR_DEPLOYMENT_ID", "demo")
    assert credit_check_configured() is True


def test_minimum_credit_cents_fails_closed_to_one_cent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CENTAUR_MINIMUM_INFERENCE_CREDIT_CENTS", "0")
    assert minimum_credit_cents() == 1

    monkeypatch.setenv("CENTAUR_MINIMUM_INFERENCE_CREDIT_CENTS", "25")
    assert minimum_credit_cents() == 25


@pytest.mark.asyncio
async def test_credit_preflight_rejects_exhausted_balance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CENTAUR_MANAGED_INFERENCE", "1")
    monkeypatch.setenv("CENTAUR_CREDIT_CHECK_URL", "https://dashboard.test/api/check")
    monkeypatch.setenv("CENTAUR_BILLING_EVENTS_SECRET", "secret")
    monkeypatch.setenv("CENTAUR_DEPLOYMENT_ID", "demo")

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, url: str, **kwargs):
            assert url == "https://dashboard.test/api/check"
            assert kwargs["headers"]["x-centaur-billing-secret"] == "secret"
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"allowed": False, "balance_cents": 0},
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    with pytest.raises(HTTPException) as exc:
        await assert_inference_credit_available()
    assert exc.value.status_code == 402


@pytest.mark.asyncio
async def test_credit_preflight_allows_funded_balance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CENTAUR_MANAGED_INFERENCE", "1")
    monkeypatch.setenv("CENTAUR_CREDIT_CHECK_URL", "https://dashboard.test/api/check")
    monkeypatch.setenv("CENTAUR_BILLING_EVENTS_SECRET", "secret")
    monkeypatch.setenv("CENTAUR_DEPLOYMENT_ID", "demo")

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, _url: str, **_kwargs):
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"allowed": True, "balance_cents": 5000},
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    await assert_inference_credit_available()
