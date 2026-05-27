"""Tenant-safe proxy for managed AI Gateway inference."""

from __future__ import annotations

import os
import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from api.billing_usage import assert_inference_credit_available
from api.deps import require_scope, verify_api_key

log = structlog.get_logger()

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

router = APIRouter(
    prefix="/ai-gateway",
    tags=["ai-gateway"],
    dependencies=[Depends(verify_api_key), Depends(require_scope("tools:*"))],
)


def _gateway_api_key() -> str:
    key = (os.getenv("AI_GATEWAY_API_KEY") or "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="AI Gateway is not configured")
    return key


def _gateway_origin() -> str:
    return (
        os.getenv("AI_GATEWAY_BASE_URL")
        or os.getenv("CENTAUR_AI_GATEWAY_UPSTREAM")
        or "https://ai-gateway.vercel.sh"
    ).rstrip("/")


def _forward_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    for name, value in request.headers.items():
        lower = name.lower()
        if lower in _HOP_BY_HOP_HEADERS:
            continue
        if lower in {"host", "authorization", "x-api-key"}:
            continue
        headers[name] = value
    headers["Authorization"] = f"Bearer {_gateway_api_key()}"

    stripe_customer_id = (os.getenv("STRIPE_CUSTOMER_ID") or "").strip()
    stripe_restricted_key = (os.getenv("STRIPE_RESTRICTED_ACCESS_KEY") or "").strip()
    if stripe_customer_id and stripe_restricted_key:
        headers["stripe-customer-id"] = stripe_customer_id
        headers["stripe-restricted-access-key"] = stripe_restricted_key
    return headers


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_ai_gateway(request: Request, path: str) -> Response:
    await assert_inference_credit_available()

    upstream_url = f"{_gateway_origin()}/{path}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    body = await request.body()
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        try:
            upstream = await client.request(
                request.method,
                upstream_url,
                headers=_forward_headers(request),
                content=body,
            )
        except httpx.HTTPError as exc:
            log.warning("ai_gateway_proxy_failed", error=str(exc), path=path)
            raise HTTPException(status_code=502, detail="AI Gateway request failed") from exc

    response_headers = {
        name: value
        for name, value in upstream.headers.items()
        if name.lower() not in _HOP_BY_HOP_HEADERS and name.lower() != "content-encoding"
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
