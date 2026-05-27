from __future__ import annotations

from starlette.requests import Request

from api.routers import ai_gateway


def _request_with_headers(headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/ai-gateway/v1/chat/completions",
            "headers": [
                (name.lower().encode("latin-1"), value.encode("latin-1"))
                for name, value in headers.items()
            ],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
        }
    )


def test_forward_headers_strip_tenant_auth_and_inject_gateway_key(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "real-gateway-key")
    monkeypatch.delenv("STRIPE_CUSTOMER_ID", raising=False)
    monkeypatch.delenv("STRIPE_RESTRICTED_ACCESS_KEY", raising=False)

    request = _request_with_headers(
        {
            "host": "tenant-api.local",
            "authorization": "Bearer sandbox-token",
            "x-api-key": "sandbox-token",
            "content-type": "application/json",
            "x-request-id": "req_123",
            "connection": "keep-alive",
        }
    )

    headers = ai_gateway._forward_headers(request)

    assert headers["Authorization"] == "Bearer real-gateway-key"
    assert headers["content-type"] == "application/json"
    assert headers["x-request-id"] == "req_123"
    assert "host" not in {name.lower() for name in headers}
    assert "x-api-key" not in {name.lower() for name in headers}
    assert "connection" not in {name.lower() for name in headers}


def test_gateway_origin_defaults_to_vercel_ai_gateway(monkeypatch) -> None:
    monkeypatch.delenv("AI_GATEWAY_BASE_URL", raising=False)
    monkeypatch.delenv("CENTAUR_AI_GATEWAY_UPSTREAM", raising=False)

    assert ai_gateway._gateway_origin() == "https://ai-gateway.vercel.sh"


def test_gateway_origin_prefers_configured_upstream_without_trailing_slash(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://gateway.example.test/")
    monkeypatch.setenv("CENTAUR_AI_GATEWAY_UPSTREAM", "https://ignored.example.test")

    assert ai_gateway._gateway_origin() == "https://gateway.example.test"
