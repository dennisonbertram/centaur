"""Readiness endpoint tests."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_readyz_reports_schema_compatibility() -> None:
    from api.routers.health import readyz

    fake_app = SimpleNamespace(state=SimpleNamespace(db_pool=object()))

    with (
        patch.dict(sys.modules, {"api.app": SimpleNamespace(app=fake_app)}),
        patch(
            "api.routers.health.check_schema_compatibility",
            new=AsyncMock(
                return_value={
                    "compatible": True,
                    "required_states_missing": [],
                    "required_columns_missing": [],
                    "required_migrations_missing": [],
                    "constraint_present": True,
                    "errors": [],
                }
            ),
        ),
        patch(
            "api.routers.health.check_runtime_credentials",
            new=AsyncMock(
                return_value={
                    "enabled": False,
                    "status": "skipped",
                    "required_keys": ["AMP_API_KEY"],
                    "missing_keys": [],
                    "errors": [],
                    "key_lengths": {},
                }
            ),
        ),
    ):
        resp = await readyz()

    assert resp.status_code == 200
    payload = json.loads(resp.body.decode("utf-8"))
    assert payload["status"] == "ok"
    assert payload["schema_compatibility"]["compatible"] is True
    assert payload["runtime_credentials"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_readyz_returns_503_when_schema_incompatible() -> None:
    from api.routers.health import readyz

    fake_app = SimpleNamespace(state=SimpleNamespace(db_pool=object()))

    incompatible = {
        "compatible": False,
        "required_states_missing": ["suspended"],
        "required_columns_missing": [],
        "required_migrations_missing": [],
        "constraint_present": True,
        "errors": [],
    }

    with (
        patch.dict(sys.modules, {"api.app": SimpleNamespace(app=fake_app)}),
        patch(
            "api.routers.health.check_schema_compatibility",
            new=AsyncMock(return_value=incompatible),
        ),
        patch(
            "api.routers.health.check_runtime_credentials",
            new=AsyncMock(
                return_value={
                    "enabled": False,
                    "status": "skipped",
                    "required_keys": ["AMP_API_KEY"],
                    "missing_keys": [],
                    "errors": [],
                    "key_lengths": {},
                }
            ),
        ),
    ):
        resp = await readyz()

    assert resp.status_code == 503
    payload = json.loads(resp.body.decode("utf-8"))
    assert payload["status"] == "not_ready"
    assert payload["schema_compatibility"]["compatible"] is False


@pytest.mark.asyncio
async def test_readyz_returns_503_when_runtime_credentials_fail() -> None:
    from api.routers.health import readyz

    fake_app = SimpleNamespace(state=SimpleNamespace(db_pool=object()))
    schema_ok = {
        "compatible": True,
        "required_states_missing": [],
        "required_columns_missing": [],
        "required_migrations_missing": [],
        "constraint_present": True,
        "errors": [],
    }
    credentials_failed = {
        "enabled": True,
        "status": "failed",
        "required_keys": ["AMP_API_KEY"],
        "missing_keys": ["AMP_API_KEY"],
        "errors": [],
        "key_lengths": {},
    }

    with (
        patch.dict(sys.modules, {"api.app": SimpleNamespace(app=fake_app)}),
        patch(
            "api.routers.health.check_schema_compatibility",
            new=AsyncMock(return_value=schema_ok),
        ),
        patch(
            "api.routers.health.check_runtime_credentials",
            new=AsyncMock(return_value=credentials_failed),
        ),
    ):
        resp = await readyz()

    assert resp.status_code == 503
    payload = json.loads(resp.body.decode("utf-8"))
    assert payload["status"] == "not_ready"
    assert payload["runtime_credentials"]["status"] == "failed"
