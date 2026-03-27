"""Unit tests for restart-safe in-flight turn replay behavior."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.sandbox.base import SandboxSession


def test_coerce_json_object_handles_jsonb_text() -> None:
    from api.agent import _coerce_json_object

    payload = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": "hello"}],
        },
    }

    assert _coerce_json_object(payload) == payload
    assert _coerce_json_object(json.dumps(payload)) == payload
    assert _coerce_json_object(json.dumps(json.dumps(payload))) == payload
    assert _coerce_json_object("not-json") is None


@pytest.mark.asyncio
async def test_replay_inflight_turn_noop_when_no_turn() -> None:
    session = SandboxSession(
        sandbox_id="sbx-1",
        thread_key="test:thread-1",
        harness="amp",
        engine="amp",
    )

    with patch(
        "api.agent._db_get_inflight_turn", new_callable=AsyncMock, return_value=None
    ):
        from api.agent import replay_inflight_turn

        result = await replay_inflight_turn(session)

    assert result == {"ok": True, "replayed": False}


@pytest.mark.asyncio
async def test_replay_inflight_turn_writes_payload() -> None:
    session = SandboxSession(
        sandbox_id="sbx-2",
        thread_key="test:thread-2",
        harness="amp",
        engine="amp",
    )
    turn_input = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": "hello"}],
        },
    }

    backend = AsyncMock()
    backend.refresh_token_by_id = AsyncMock()
    backend.attach = AsyncMock()
    backend.write_stdin = AsyncMock()

    with (
        patch(
            "api.agent._db_get_inflight_turn",
            new_callable=AsyncMock,
            return_value=("turn-abc", turn_input, 1),
        ),
        patch(
            "api.agent._db_set_inflight_turn", new_callable=AsyncMock
        ) as set_inflight,
        patch("api.agent._db_update_state", new_callable=AsyncMock),
        patch("api.agent.get_backend", return_value=backend),
        patch("api.agent.mint_sandbox_token", return_value="sbx-token"),
    ):
        from api.agent import replay_inflight_turn

        result = await replay_inflight_turn(session)

    assert result["ok"] is True
    assert result["replayed"] is True
    assert result["durable_turn_id"] == "turn-abc"
    backend.write_stdin.assert_awaited_once_with(session, turn_input)
    set_inflight.assert_awaited_once_with(
        session.thread_key,
        "turn-abc",
        turn_input,
        attempts=2,
    )


@pytest.mark.asyncio
async def test_inject_stdin_persists_inflight_turn() -> None:
    session = SandboxSession(
        sandbox_id="sbx-3",
        thread_key="test:thread-3",
        harness="amp",
        engine="amp",
    )

    backend = AsyncMock()
    backend.refresh_token_by_id = AsyncMock()
    backend.attach = AsyncMock()
    backend.write_stdin = AsyncMock()

    with (
        patch("api.agent._insert_system_message", new_callable=AsyncMock),
        patch(
            "api.agent._get_last_delivered_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("api.agent._flush_pending", new_callable=AsyncMock, return_value=[]),
        patch(
            "api.agent._db_set_inflight_turn", new_callable=AsyncMock
        ) as set_inflight,
        patch("api.agent._db_update_state", new_callable=AsyncMock),
        patch("api.agent._advance_cursor", new_callable=AsyncMock),
        patch("api.agent.get_backend", return_value=backend),
        patch("api.agent.mint_sandbox_token", return_value="sbx-token"),
    ):
        from api.agent import inject_stdin

        result = await inject_stdin(session, "hello")

    assert result["ok"] is True
    assert result["injected"] is True
    assert result["durable_turn_id"].startswith("turn-")
    set_inflight.assert_awaited_once()
