#!/usr/bin/env python3
"""amp-wrapper — transparent context management for amp.

Makes amp's context window invisible to consumers. Two mechanisms:

  1. Auto-chain: when context usage hits CONTEXT_THRESHOLD, the wrapper
     kills amp after the current turn and continues in a fresh thread.
     The consumer never knows — output just keeps streaming.

  2. Handoff chain: when amp calls handoff(follow=true), the wrapper
     suppresses the handoff noise and chains into the new thread.

In both cases the stdout consumer sees one uninterrupted stream.

Set AMP_CONTEXT_THRESHOLD env var to override the default (0.85).
"""

import json
import os
import re
import signal
import subprocess
import sys

AMP = ["amp", "--no-ide", "--no-notifications", "--dangerously-allow-all",
       "--execute", "--stream-json", "--stream-json-input"]
TID_RE = re.compile(r"T-[a-f0-9-]+")
THRESHOLD = float(os.environ.get("AMP_CONTEXT_THRESHOLD", "0.85"))


def emit(line):
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def usage_pct(evt):
    """Return context utilization 0.0–1.0 from an assistant event's usage."""
    u = evt.get("message", {}).get("usage", {})
    mx = u.get("max_tokens", 0)
    if not mx:
        return 0.0
    return (u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            + u.get("cache_read_input_tokens", 0) + u.get("output_tokens", 0)) / mx


def is_end_turn(evt):
    return evt.get("message", {}).get("stop_reason") == "end_turn"


def has_handoff(evt):
    """Check if an assistant event contains a handoff(follow=true) tool call."""
    for b in evt.get("message", {}).get("content", []):
        if b.get("name") == "handoff" and b.get("input", {}).get("follow"):
            return True
    return False


def extract_handoff_tid(evt):
    """Extract newThreadID from a tool result event."""
    s = json.dumps(evt)
    if "newThreadID" not in s:
        return None
    m = TID_RE.search(s.split("newThreadID")[1])
    return m.group(0) if m else None


def run(cmd, stdin_data=None):
    """Run amp, stream stdout, handle chaining triggers.

    Returns (exit_code, next_thread_id | None).
    """
    kw = dict(stdout=subprocess.PIPE, stderr=sys.stderr, text=True, bufsize=1)
    if stdin_data:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, **kw)
        p.stdin.write(stdin_data)
        p.stdin.close()
    else:
        p = subprocess.Popen(cmd, stdin=sys.stdin, **kw)

    session_id = None
    handoff_tid = None
    suppressing = False
    needs_auto_chain = False

    while True:
        raw = p.stdout.readline()
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

        t = evt.get("type", "")

        # Never forward `result` events — the API fires turn.done on end_turn
        if t == "result" and not suppressing:
            # But still use it for auto-chain: if we flagged context pressure
            # on the preceding end_turn, this is our cue to kill and chain
            if needs_auto_chain:
                p.kill()
                p.wait()
                return 0, session_id
            continue

        # Track session id from init events
        if t == "system" and evt.get("subtype") == "init":
            session_id = evt.get("session_id") or session_id

        # ── Handoff: detect, extract tid, suppress, kill ─────────
        if not suppressing and t == "assistant" and has_handoff(evt):
            suppressing = True

        if suppressing and not handoff_tid and t in ("user", "tool"):
            handoff_tid = extract_handoff_tid(evt)

        if suppressing:
            if handoff_tid and t == "assistant" and is_end_turn(evt):
                p.kill()
                break
            continue

        # ── Auto-chain: flag context pressure on end_turn ──────
        if t == "assistant" and is_end_turn(evt) and usage_pct(evt) >= THRESHOLD:
            needs_auto_chain = True

        emit(line)

    p.wait()
    return (0, handoff_tid) if handoff_tid else (p.returncode or 0, None)


CONTINUE_MSG = json.dumps({"type": "user", "message": {"role": "user",
    "content": [{"type": "text", "text": "continue"}]}}) + "\n"


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    code, nxt = run(AMP)
    while nxt:
        code, nxt = run(AMP + ["threads", "continue", nxt], stdin_data=CONTINUE_MSG)
    sys.exit(code)


if __name__ == "__main__":
    main()
