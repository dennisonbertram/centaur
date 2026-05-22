from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class FakeWorkflowContext:
    run_id = "wfr_unit"
    run_input: dict = {}
    _pool = object()

    def _peek_resolved_name(self, name: str) -> str:
        return name

    async def step(self, _name, fn, **_kwargs):
        return await fn()


@pytest.mark.asyncio
async def test_slack_agent_turn_inserts_requester_context_before_messages():
    from api.workflow_engine import Delivery, SuspendWorkflow, do_agent_turn

    calls: list[str] = []

    async def fake_insert_system_message(thread_key, platform, *, user_id=None):
        calls.append("system")
        assert thread_key == "slack:T123:C123:1.23"
        assert platform == "slack"
        assert user_id == "U123"

    async def fake_append_message(*_args, **_kwargs):
        calls.append("message")
        return {"ok": True, "message_id": "msg"}

    with (
        patch(
            "api.workflow_engine.spawn_assignment",
            new=AsyncMock(return_value={"assignment_generation": 1}),
        ),
        patch(
            "api.workflow_engine._compute_agent_session_title",
            new=AsyncMock(return_value="Centaur"),
        ),
        patch(
            "api.workflow_engine._compute_agent_session_header",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "api.workflow_engine.slackbot_client.open_agent_session",
            new=AsyncMock(return_value=None),
        ),
        patch("api.workflow_engine.append_message", new=AsyncMock(side_effect=fake_append_message)),
        patch(
            "api.workflow_engine.enqueue_execution",
            new=AsyncMock(return_value={"execution_id": "exe_unit", "status": "queued"}),
        ),
        patch("api.workflow_engine.get_execution", new=AsyncMock(return_value=None)),
        patch("api.agent._insert_system_message", new=AsyncMock(side_effect=fake_insert_system_message)),
    ):
        with pytest.raises(SuspendWorkflow):
            await do_agent_turn(
                FakeWorkflowContext(),
                thread_key="slack:T123:C123:1.23",
                parts=[{"type": "text", "text": "hello"}],
                message_id="slack:T123:C123:1.23",
                user_id="U123",
                delivery=Delivery.slack("C123", "1.23", user_id="U123"),
            )

    assert calls == ["system", "message"]
