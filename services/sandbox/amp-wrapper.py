#!/usr/bin/env python3
"""amp-wrapper — stable NDJSON bridge for Amp inside sandbox containers.

Responsibilities:
1. Run Amp in streaming JSON mode with deterministic defaults.
2. Keep follow=true handoffs seamless by chaining into the new thread.
3. Recover from transient Amp crashes without killing the container.
4. Optionally continue a prior Amp thread on cold start via AMP_CONTINUE_THREAD_ID.
"""

import json
import os
import re
import signal
import subprocess
import sys

TID_RE = re.compile(r"T-[a-f0-9-]+")


def _amp_subprocess_env() -> dict[str, str]:
    """Build env for amp child processes.

    Amp currently runs on Bun, and in this sandbox setup Bun does not reliably
    trust the injected firewall CA for HTTPS MITM proxying. Keep the TLS bypass
    scoped to amp-wrapper-managed amp processes so other harnesses are
    unaffected.
    """
    env = os.environ.copy()
    if env.get("HTTPS_PROXY") and "NODE_TLS_REJECT_UNAUTHORIZED" not in env:
        env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
    return env


def _amp_base_cmd() -> list[str]:
    mode = (os.environ.get("AMP_MODE") or "deep").strip() or "deep"
    return [
        "amp",
        "--no-ide",
        "--no-notifications",
        "--dangerously-allow-all",
        "--execute",
        "--stream-json",
        "--stream-json-input",
        "--stream-json-thinking",
        "--mode",
        mode,
    ]


AMP_BASE = _amp_base_cmd()


def emit(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def is_end_turn(evt: dict) -> bool:
    return evt.get("message", {}).get("stop_reason") == "end_turn"


def has_handoff(evt: dict) -> bool:
    """Check if an assistant event contains a handoff(follow=true) tool call."""
    for block in evt.get("message", {}).get("content", []):
        if block.get("name") == "handoff" and block.get("input", {}).get("follow"):
            return True
    return False


def extract_handoff_tid(evt: dict) -> str | None:
    """Extract newThreadID from a tool result event."""
    payload = json.dumps(evt)
    if "newThreadID" not in payload:
        return None
    match = TID_RE.search(payload.split("newThreadID", 1)[1])
    return match.group(0) if match else None


class RunResult:
    __slots__ = ("code", "chain_tid")

    def __init__(self, code: int, chain_tid: str | None = None):
        self.code = code
        self.chain_tid = chain_tid


def run(cmd: list[str], stdin_data: str | None = None) -> RunResult:
    """Run Amp, stream stdout, and detect handoff chaining."""
    kw = dict(
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        bufsize=1,
        env=_amp_subprocess_env(),
    )
    if stdin_data:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, **kw)
        assert proc.stdin is not None
        proc.stdin.write(stdin_data)
        proc.stdin.close()
    else:
        proc = subprocess.Popen(cmd, stdin=sys.stdin, **kw)

    handoff_tid = None
    suppressing = False

    while True:
        raw = proc.stdout.readline()
        if not raw:
            break
        line = raw.rstrip("\n")
        if not line:
            continue

        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            if not suppressing:
                emit(line)
            continue

        evt_type = evt.get("type", "")

        # Keep successful result handling centralized in API _stream_stdout
        # turn.done synthesis. Error results are forwarded so API can persist a
        # terminal state instead of hanging until stream EOF.
        if evt_type == "result" and not suppressing:
            subtype = evt.get("subtype")
            if not evt.get("is_error") and subtype in (None, "", "success"):
                continue

        if not suppressing and evt_type == "assistant" and has_handoff(evt):
            suppressing = True

        if suppressing and not handoff_tid and evt_type in ("user", "tool"):
            handoff_tid = extract_handoff_tid(evt)

        if suppressing:
            # Wait until the handoff turn naturally ends, then chain into new thread.
            if handoff_tid and evt_type == "assistant" and is_end_turn(evt):
                proc.kill()
                break
            continue

        emit(line)

    proc.wait()
    if handoff_tid:
        return RunResult(0, chain_tid=handoff_tid)
    return RunResult(proc.returncode or 0)


CONTINUE_MSG = json.dumps({
    "type": "user",
    "message": {
        "role": "user",
        "content": [{"type": "text", "text": "continue"}],
    },
}) + "\n"

MAX_CRASH_RESTARTS = 5


def main() -> None:
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    startup_tid = (os.environ.get("AMP_CONTINUE_THREAD_ID") or "").strip()
    first_cmd = AMP_BASE + ["threads", "continue", startup_tid] if startup_tid else AMP_BASE

    crashes = 0
    code = 0
    next_cmd = first_cmd

    while True:
        result = run(next_cmd)
        next_cmd = AMP_BASE

        while result.chain_tid:
            crashes = 0
            result = run(
                AMP_BASE + ["threads", "continue", result.chain_tid],
                stdin_data=CONTINUE_MSG,
            )

        if result.code == 0:
            break

        crashes += 1
        if crashes > MAX_CRASH_RESTARTS:
            emit(json.dumps({
                "type": "error",
                "error": {"message": f"amp crashed {crashes} times, giving up"},
            }))
            code = result.code
            break

        emit(json.dumps({
            "type": "error",
            "error": {
                "message": (
                    f"amp exited with code {result.code}, "
                    f"restarting ({crashes}/{MAX_CRASH_RESTARTS})"
                )
            },
        }))

    sys.exit(code)


if __name__ == "__main__":
    main()
