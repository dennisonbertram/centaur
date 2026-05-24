from __future__ import annotations

import uuid

import httpx
import pytest


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.mark.asyncio
async def test_list_workflows_returns_catalog_with_webhook_metadata(
    client,
    tmp_path,
    monkeypatch,
):
    from api.workflow_engine import discover_workflow_handlers

    workflow_name = f"catalog_{uuid.uuid4().hex}"
    slug = f"catalog-{uuid.uuid4().hex}"
    workflow_file = tmp_path / "catalog_workflow.py"
    workflow_file.write_text(
        "from dataclasses import dataclass\n"
        "from api.webhooks import HmacAuth\n"
        f"WORKFLOW_NAME = {workflow_name!r}\n"
        "SCHEDULE = {'interval_seconds': 300, 'no_delivery': True}\n"
        "WEBHOOKS = [{\n"
        f"    'slug': {slug!r},\n"
        "    'provider': 'test',\n"
        "    'auth': HmacAuth.github(secret_ref='CATALOG_WEBHOOK_SECRET'),\n"
        "    'trigger_key': {'type': 'header', 'header': 'X-Test-Delivery'},\n"
        "}]\n"
        "@dataclass\n"
        "class Input:\n"
        "    message: str\n"
        "    count: int = 1\n"
        "async def handler(inp, ctx):\n"
        "    return {}\n",
    )
    monkeypatch.setenv("WORKFLOW_DIRS", str(tmp_path))
    discover_workflow_handlers()

    response = await client.get("/workflows")

    assert response.status_code == 200
    body = response.json()
    item = next(item for item in body["items"] if item["workflow_name"] == workflow_name)
    assert item["schedule"]["interval_seconds"] == 300
    assert item["input_type"] == "Input"
    assert item["input_fields"] == [
        {"name": "message", "type": "str", "required": True},
        {"name": "count", "type": "int", "required": False},
    ]
    assert item["webhooks"] == [
        {
            "slug": slug,
            "path": f"/api/webhooks/{slug}",
            "provider": "test",
            "auth": {
                "type": "hmac",
                "algorithm": "sha256",
                "signature_header": "X-Hub-Signature-256",
                "signature_prefix": "sha256=",
                "encoding": "hex",
            },
            "trigger_key": {"type": "header", "header": "X-Test-Delivery"},
            "allowed_methods": ["POST"],
            "allowed_content_types": ["application/json"],
        }
    ]
    assert "CATALOG_WEBHOOK_SECRET" not in str(item)

    detail_response = await client.get(f"/workflows/{workflow_name}")
    assert detail_response.status_code == 200
    assert detail_response.json()["item"]["workflow_name"] == workflow_name


@pytest.mark.asyncio
async def test_list_workflows_filters_to_key_scopes(
    client,
    managed_app,
    api_key: str,
):
    create_response = await client.post(
        "/admin/api-keys",
        headers=_auth(api_key),
        json={
            "name": f"workflow-catalog-{uuid.uuid4().hex}",
            "scopes": ["workflows:agent_turn"],
            "created_by": "pytest",
        },
    )
    assert create_response.status_code == 200
    plaintext_key = create_response.json()["key"]

    transport = httpx.ASGITransport(app=managed_app, client=("198.51.100.10", 49152))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as external:
        response = await external.get("/workflows", headers=_auth(plaintext_key))
        assert response.status_code == 200
        names = [item["workflow_name"] for item in response.json()["items"]]
        assert names == ["agent_turn"]

        allowed = await external.get("/workflows/agent_turn", headers=_auth(plaintext_key))
        assert allowed.status_code == 200

        forbidden = await external.get(
            "/workflows/slack_thread_turn",
            headers=_auth(plaintext_key),
        )
        assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_workflow_catalog_does_not_shadow_run_routes(client, api_key: str):
    response = await client.get("/workflows/runs", headers=_auth(api_key))
    assert response.status_code == 200
    assert response.json()["ok"] is True
