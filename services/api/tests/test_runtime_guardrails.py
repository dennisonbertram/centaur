from __future__ import annotations

from unittest.mock import patch

import pytest


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, responses: dict[str, _FakeResponse]):
        self._responses = responses
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, headers: dict[str, str] | None = None):
        self.calls.append((url, headers))
        return self._responses[url]


@pytest.mark.asyncio
async def test_check_runtime_credentials_skipped_when_guard_disabled() -> None:
    from api.runtime_guardrails import check_runtime_credentials

    with patch.dict(
        "os.environ",
        {
            "RUNTIME_CREDENTIAL_GUARD_ENABLED": "0",
            "REQUIRED_RUNTIME_SECRET_KEYS": "AMP_API_KEY",
        },
        clear=True,
    ):
        report = await check_runtime_credentials()

    assert report["enabled"] is False
    assert report["status"] == "skipped"
    assert report["required_keys"] == ["AMP_API_KEY"]
    assert report["probe_keys"] == []
    assert report["invalid_keys"] == []


@pytest.mark.asyncio
async def test_check_runtime_credentials_ok_when_key_present() -> None:
    from api.runtime_guardrails import check_runtime_credentials

    base = "http://firewall:8081"
    url = f"{base}/secrets/AMP_API_KEY"
    fake_client = _FakeClient({url: _FakeResponse(200, {"value": "abc123"})})

    with (
        patch.dict(
            "os.environ",
            {
                "FIREWALL_CONTROL_TOKEN": "control-token",
                "RUNTIME_CREDENTIAL_GUARD_ENABLED": "1",
                "REQUIRED_RUNTIME_SECRET_KEYS": "AMP_API_KEY",
                "FIREWALL_HEALTH_URL": base,
            },
            clear=True,
        ),
        patch(
            "api.runtime_guardrails.httpx.AsyncClient",
            return_value=fake_client,
        ),
    ):
        report = await check_runtime_credentials()

    assert report["enabled"] is True
    assert report["status"] == "ok"
    assert report["checked_keys"] == ["AMP_API_KEY"]
    assert report["probe_keys"] == []
    assert report["invalid_keys"] == []
    assert report["key_lengths"] == {"AMP_API_KEY": 6}
    assert fake_client.calls == [(url, {"Authorization": "Bearer control-token"})]


@pytest.mark.asyncio
async def test_check_runtime_credentials_sends_bearer_when_token_set() -> None:
    """Verify the firewall control token is sent as Authorization: Bearer."""
    from api.runtime_guardrails import check_runtime_credentials

    base = "http://firewall:8081"
    url = f"{base}/secrets/AMP_API_KEY"
    fake = _FakeClient({url: _FakeResponse(200, {"value": "abc"})})

    with (
        patch.dict(
            "os.environ",
            {
                "RUNTIME_CREDENTIAL_GUARD_ENABLED": "1",
                "REQUIRED_RUNTIME_SECRET_KEYS": "AMP_API_KEY",
                "FIREWALL_HEALTH_URL": base,
                "FIREWALL_CONTROL_TOKEN": "test-token-xyz",
            },
            clear=True,
        ),
        patch(
            "api.runtime_guardrails.httpx.AsyncClient",
            return_value=fake,
        ),
    ):
        await check_runtime_credentials()

    assert fake.calls == [(url, {"Authorization": "Bearer test-token-xyz"})]


@pytest.mark.asyncio
async def test_check_runtime_credentials_marks_openai_key_invalid_on_401() -> None:
    from api.runtime_guardrails import check_runtime_credentials

    base = "http://firewall:8081"
    secret_url = f"{base}/secrets/OPENAI_API_KEY"
    probe_url = "https://api.openai.com/v1/models"
    fake_client = _FakeClient(
        {
            secret_url: _FakeResponse(200, {"value": "sk-live-valid-format"}),
            probe_url: _FakeResponse(401, {"error": {"message": "Incorrect API key"}}),
        }
    )

    with (
        patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "configured",
                "RUNTIME_CREDENTIAL_GUARD_ENABLED": "1",
                "REQUIRED_RUNTIME_SECRET_KEYS": "OPENAI_API_KEY",
                "FIREWALL_HEALTH_URL": base,
            },
            clear=True,
        ),
        patch(
            "api.runtime_guardrails.httpx.AsyncClient",
            return_value=fake_client,
        ),
    ):
        report = await check_runtime_credentials()

    assert report["status"] == "failed"
    assert report["missing_keys"] == []
    assert report["invalid_keys"] == ["OPENAI_API_KEY"]
    assert report["probe_keys"] == ["OPENAI_API_KEY"]
    assert report["keys"]["OPENAI_API_KEY"] == {
        "status": "invalid",
        "length": 20,
        "provider": "openai",
        "probe_status": "invalid",
        "probe_http_status": 401,
    }
    assert fake_client.calls == [
        (secret_url, {}),
        (probe_url, {"Authorization": "Bearer sk-live-valid-format"}),
    ]


@pytest.mark.asyncio
async def test_check_runtime_credentials_marks_anthropic_key_invalid_on_403() -> None:
    from api.runtime_guardrails import check_runtime_credentials

    base = "http://firewall:8081"
    secret_url = f"{base}/secrets/ANTHROPIC_API_KEY"
    probe_url = "https://api.anthropic.com/v1/models"
    fake_client = _FakeClient(
        {
            secret_url: _FakeResponse(200, {"value": "sk-ant-api03-valid-format"}),
            probe_url: _FakeResponse(403, {"error": {"message": "forbidden"}}),
        }
    )

    with (
        patch.dict(
            "os.environ",
            {
                "ANTHROPIC_API_KEY": "configured",
                "RUNTIME_CREDENTIAL_GUARD_ENABLED": "1",
                "REQUIRED_RUNTIME_SECRET_KEYS": "ANTHROPIC_API_KEY",
                "FIREWALL_HEALTH_URL": base,
            },
            clear=True,
        ),
        patch(
            "api.runtime_guardrails.httpx.AsyncClient",
            return_value=fake_client,
        ),
    ):
        report = await check_runtime_credentials()

    assert report["status"] == "failed"
    assert report["invalid_keys"] == ["ANTHROPIC_API_KEY"]
    assert report["keys"]["ANTHROPIC_API_KEY"] == {
        "status": "invalid",
        "length": 25,
        "provider": "anthropic",
        "probe_status": "invalid",
        "probe_http_status": 403,
    }
    assert fake_client.calls == [
        (secret_url, {}),
        (
            probe_url,
            {
                "x-api-key": "sk-ant-api03-valid-format",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        ),
    ]


@pytest.mark.asyncio
async def test_assert_runtime_credentials_ready_raises_when_missing() -> None:
    from api.runtime_guardrails import assert_runtime_credentials_ready

    base = "http://firewall:8081"
    url = f"{base}/secrets/AMP_API_KEY"

    with (
        patch.dict(
            "os.environ",
            {
                "RUNTIME_CREDENTIAL_GUARD_ENABLED": "1",
                "REQUIRED_RUNTIME_SECRET_KEYS": "AMP_API_KEY",
                "FIREWALL_HEALTH_URL": base,
            },
            clear=True,
        ),
        patch(
            "api.runtime_guardrails.httpx.AsyncClient",
            return_value=_FakeClient({url: _FakeResponse(404, {"error": "not found"})}),
        ),
    ):
        with pytest.raises(RuntimeError, match="runtime credential guard failed"):
            await assert_runtime_credentials_ready()


@pytest.mark.asyncio
async def test_assert_runtime_credentials_ready_raises_when_provider_key_invalid() -> None:
    from api.runtime_guardrails import assert_runtime_credentials_ready

    base = "http://firewall:8081"
    secret_url = f"{base}/secrets/OPENAI_API_KEY"
    probe_url = "https://api.openai.com/v1/models"
    fake_client = _FakeClient(
        {
            secret_url: _FakeResponse(200, {"value": "sk-live-valid-format"}),
            probe_url: _FakeResponse(401, {"error": {"message": "Incorrect API key"}}),
        }
    )

    with (
        patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "configured",
                "RUNTIME_CREDENTIAL_GUARD_ENABLED": "1",
                "REQUIRED_RUNTIME_SECRET_KEYS": "OPENAI_API_KEY",
                "FIREWALL_HEALTH_URL": base,
            },
            clear=True,
        ),
        patch(
            "api.runtime_guardrails.httpx.AsyncClient",
            return_value=fake_client,
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match="runtime credential guard failed invalid_keys=OPENAI_API_KEY",
        ):
            await assert_runtime_credentials_ready()
