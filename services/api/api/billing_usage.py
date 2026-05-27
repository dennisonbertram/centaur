"""Best-effort reporting of managed inference usage to the dashboard billing API."""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

log = structlog.get_logger()


def managed_inference_enabled() -> bool:
    return (os.getenv("CENTAUR_MANAGED_INFERENCE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def billing_events_configured() -> bool:
    return bool(
        (os.getenv("CENTAUR_BILLING_EVENTS_URL") or "").strip()
        and (os.getenv("CENTAUR_BILLING_EVENTS_SECRET") or "").strip()
        and (os.getenv("CENTAUR_DEPLOYMENT_ID") or "").strip()
    )


def credit_check_configured() -> bool:
    return bool(
        (os.getenv("CENTAUR_CREDIT_CHECK_URL") or "").strip()
        and (os.getenv("CENTAUR_BILLING_EVENTS_SECRET") or "").strip()
        and (os.getenv("CENTAUR_DEPLOYMENT_ID") or "").strip()
    )


def minimum_credit_cents() -> int:
    raw = (os.getenv("CENTAUR_MINIMUM_INFERENCE_CREDIT_CENTS") or "1").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 1
    return max(parsed, 1)


async def assert_inference_credit_available() -> None:
    if not managed_inference_enabled():
        return
    if not credit_check_configured():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="Managed inference credit checks are not configured",
        )

    from fastapi import HTTPException

    url = (os.getenv("CENTAUR_CREDIT_CHECK_URL") or "").strip().rstrip("/")
    secret = (os.getenv("CENTAUR_BILLING_EVENTS_SECRET") or "").strip()
    deployment_id = (os.getenv("CENTAUR_DEPLOYMENT_ID") or "").strip()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            response = await client.post(
                url,
                json={
                    "deployment_id": deployment_id,
                    "minimum_credit_cents": minimum_credit_cents(),
                },
                headers={"x-centaur-billing-secret": secret},
            )
            response.raise_for_status()
            payload = response.json()
    except HTTPException:
        raise
    except Exception as exc:
        log.warning(
            "billing_credit_check_failed",
            deployment_id=deployment_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail="Managed inference credit check failed",
        ) from exc

    if not bool(payload.get("allowed")):
        raise HTTPException(
            status_code=402,
            detail="Managed inference credits are exhausted",
        )


async def report_inference_usage(
    *,
    execution_id: str,
    event_id: int,
    usage_metrics: dict[str, Any],
) -> None:
    if not managed_inference_enabled() or not billing_events_configured():
        return

    url = (os.getenv("CENTAUR_BILLING_EVENTS_URL") or "").strip().rstrip("/")
    secret = (os.getenv("CENTAUR_BILLING_EVENTS_SECRET") or "").strip()
    deployment_id = (os.getenv("CENTAUR_DEPLOYMENT_ID") or "").strip()
    idempotency_key = f"{deployment_id}:{execution_id}:{event_id}"
    payload = {
        "deployment_id": deployment_id,
        "execution_id": execution_id,
        "event_id": event_id,
        "idempotency_key": idempotency_key,
        "model": usage_metrics.get("model"),
        "input_tokens": usage_metrics.get("input_tokens", 0),
        "output_tokens": usage_metrics.get("output_tokens", 0),
        "cache_creation_input_tokens": usage_metrics.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": usage_metrics.get("cache_read_input_tokens", 0),
        "cost_usd": usage_metrics.get("cost_usd", 0),
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"x-centaur-billing-secret": secret},
            )
            response.raise_for_status()
    except Exception as exc:
        log.warning(
            "billing_usage_report_failed",
            deployment_id=deployment_id,
            execution_id=execution_id,
            event_id=event_id,
            error=str(exc),
        )
