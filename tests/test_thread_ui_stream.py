from __future__ import annotations

from api.routers.threads import _ui_stream_chunks_for_event


def test_subagent_stream_chunk_preserves_event_seq_and_activity() -> None:
    chunks = _ui_stream_chunks_for_event(
        3,
        7,
        {
            "type": "subagent",
            "event_seq": 42,
            "subagent_id": "task-123",
            "status": "working",
            "name": "Research lending markets",
            "activity": "Reading Aave docs",
            "tool_name": "ReadFile",
        },
    )

    assert chunks == [
        {
            "type": "data-subagent",
            "id": "turn-3-subagent-task-123-working",
            "data": {
                "subagent_id": "task-123",
                "phase": None,
                "status": "working",
                "name": "Research lending markets",
                "summary": None,
                "error": None,
                "branch_index": None,
                "total_branches": None,
                "completed": None,
                "acceptable": None,
                "failed": None,
                "completed_count": None,
                "acceptable_count": None,
                "failed_count": None,
                "is_acceptable": None,
                "turns": None,
                "tool_calls": None,
                "duration_s": None,
                "max_parallel": None,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "cost_usd": None,
                "model": None,
                "activity": "Reading Aave docs",
                "tool_name": "ReadFile",
                "event_seq": 42,
            },
        }
    ]
