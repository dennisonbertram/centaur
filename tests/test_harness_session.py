"""Tests for sandbox/harness_session.py — verifies the NDJSON stdin/stdout protocol."""

import io
import json
import subprocess
import sys
import threading
import types
from unittest import mock

import pytest

# Import the module from sandbox/
sys.path.insert(0, "sandbox")
import harness_session as hs


def _lines(output: io.StringIO) -> list[dict]:
    """Parse NDJSON lines from captured stdout."""
    output.seek(0)
    results = []
    for line in output:
        line = line.strip()
        if line:
            results.append(json.loads(line))
    return results


class TestBuildPersistentCmd:
    def test_amp_no_message_arg(self):
        """amp command must NOT include -x <message> — messages go via stdin."""
        hs.engine = "amp"
        hs.model_override = ""
        cmd = hs.build_persistent_cmd()
        assert "--execute" in cmd
        assert "--stream-json" in cmd
        assert "--stream-json-input" in cmd
        # No -x with a message value
        assert "-x" not in cmd
        # No positional message arg after the flags
        flag_indices = [i for i, c in enumerate(cmd) if c.startswith("-")]
        # Everything should be a flag
        for c in cmd[1:]:  # skip "amp"
            assert c.startswith("-") or c.startswith("--"), f"unexpected positional arg: {c}"

    def test_amp_with_model(self):
        hs.engine = "amp"
        hs.model_override = "claude-sonnet-4-20250514"
        cmd = hs.build_persistent_cmd()
        assert "--model" in cmd
        assert "claude-sonnet-4-20250514" in cmd

    def test_claude_code_no_message_arg(self):
        hs.engine = "claude-code"
        hs.model_override = ""
        cmd = hs.build_persistent_cmd()
        assert "claude" == cmd[0]
        assert "--output-format" in cmd
        assert "-p" not in cmd


class TestBuildOneshotCmd:
    def test_codex(self):
        hs.engine = "codex"
        hs.model_override = ""
        cmd = hs.build_oneshot_cmd("do stuff", None)
        assert cmd[0] == "codex"
        assert "do stuff" in cmd

    def test_codex_resume(self):
        hs.engine = "codex"
        hs.model_override = ""
        cmd = hs.build_oneshot_cmd("do stuff", "thread-123")
        assert "resume" in cmd
        assert "thread-123" in cmd


class TestProtocol:
    """Test the NDJSON stdin→stdout protocol without real harness processes."""

    def _run_session(self, engine: str, stdin_messages: list[dict], mock_stdout_lines: list[str]):
        """Run harness_session with mocked subprocess and stdin."""
        hs.engine = engine
        hs.model_override = ""
        hs.proc = None
        hs.agent_thread_id = None
        hs.current_turn_id = None
        hs.last_result_text = None

        captured = io.StringIO()

        # Mock stdin
        stdin_text = "\n".join(json.dumps(m) for m in stdin_messages) + "\n"

        # Mock subprocess that produces mock_stdout_lines
        mock_proc = mock.MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = None
        mock_proc.stdin = io.StringIO()
        mock_proc.stdout = iter(mock_stdout_lines)
        mock_proc.stderr = iter([])
        mock_proc.returncode = 0

        with mock.patch.object(hs, "start_harness", return_value=mock_proc):
            with mock.patch("sys.stdin", io.StringIO(stdin_text)):
                with mock.patch("sys.stdout", captured):
                    if engine in ("amp", "claude-code"):
                        hs.run_persistent()
                    else:
                        hs.run_oneshot()

        return _lines(captured), mock_proc

    def test_amp_turn_emits_ready_and_forwards(self):
        """First turn should start harness, forward events, emit turn.done on assistant end_turn."""
        harness_output = [
            json.dumps({"type": "system", "subtype": "init", "session_id": "s1"}) + "\n",
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}], "stop_reason": "end_turn"}}) + "\n",
        ]
        events, mock_proc = self._run_session(
            "amp",
            [{"type": "turn.start", "turn_id": 1, "text": "hello"}],
            harness_output,
        )

        types = [e["type"] for e in events]
        assert "system" in types
        assert "assistant" in types
        assert "turn.done" in types

        turn_done = next(e for e in events if e["type"] == "turn.done")
        assert turn_done["turn_id"] == 1
        assert turn_done["result"] == "hi"
        assert turn_done["agent_thread_id"] == "s1"

    def test_amp_message_sent_via_stdin(self):
        """Message should be written to harness stdin, not as CLI arg."""
        harness_output = [
            json.dumps({"type": "result", "result": "done"}) + "\n",
        ]
        events, mock_proc = self._run_session(
            "amp",
            [{"type": "turn.start", "turn_id": 1, "text": "do something"}],
            harness_output,
        )

        # Check that stdin got the user message in amp's expected format
        stdin_content = mock_proc.stdin.getvalue()
        written = json.loads(stdin_content.strip())
        assert written["type"] == "user"
        assert written["message"]["role"] == "user"
        assert written["message"]["content"][0]["text"] == "do something"

    def test_ping_pong(self):
        """Ping should be answered with pong without starting harness."""
        hs.engine = "amp"
        hs.model_override = ""
        hs.proc = None

        captured = io.StringIO()
        stdin_text = json.dumps({"type": "ping"}) + "\n"

        with mock.patch("sys.stdin", io.StringIO(stdin_text)):
            with mock.patch("sys.stdout", captured):
                hs.run_persistent()

        events = _lines(captured)
        assert len(events) == 1
        assert events[0]["type"] == "pong"
