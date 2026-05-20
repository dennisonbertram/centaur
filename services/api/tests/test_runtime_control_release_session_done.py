"""Tests for the eager slackbot session_done dispatch on release_assignment."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest


def _row(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return {"metadata": json.dumps(metadata) if metadata is not None else None}


def test_collect_slackbot_session_ids_dedupes_and_skips_blanks():
    from api.runtime_control import _collect_slackbot_session_ids

    rows = [
        _row({"slackbot_agent_session_id": "sess_a"}),
        _row({"slackbot_agent_session_id": "sess_a"}),
        _row({"slackbot_agent_session_id": "sess_b"}),
        _row({"slackbot_agent_session_id": "  "}),
        _row({}),
        _row(None),
    ]

    assert _collect_slackbot_session_ids(rows) == ["sess_a", "sess_b"]


@pytest.mark.asyncio
async def test_close_slackbot_sessions_on_release_calls_session_done(monkeypatch):
    from api import runtime_control

    session_done = AsyncMock(return_value=None)
    monkeypatch.setattr(runtime_control.slackbot_client, "session_done", session_done)

    await runtime_control._close_slackbot_sessions_on_release(
        thread_key="slack:T:C:1.0",
        release_id="rel-1",
        session_ids=["sess_a", "sess_b"],
    )

    assert session_done.await_count == 2
    assert [call.args[0] for call in session_done.await_args_list] == ["sess_a", "sess_b"]


@pytest.mark.asyncio
async def test_close_slackbot_sessions_on_release_swallows_errors(monkeypatch, caplog):
    from api import runtime_control

    async def _boom(_session_id: str) -> None:
        raise RuntimeError("network down")

    monkeypatch.setattr(runtime_control.slackbot_client, "session_done", _boom)

    await runtime_control._close_slackbot_sessions_on_release(
        thread_key="slack:T:C:1.0",
        release_id="rel-1",
        session_ids=["sess_a"],
    )
