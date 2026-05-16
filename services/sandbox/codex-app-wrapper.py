#!/usr/bin/env python3
"""Centaur NDJSON bridge for Codex through the Python app-server SDK."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import shutil
import signal
import sys
from typing import Any

from pydantic import BaseModel


class IgnoredResponse(BaseModel):
    pass


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _payload_dict(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        dumped = payload.model_dump(by_alias=True, exclude_none=True, mode="json")
        return dumped if isinstance(dumped, dict) else {}
    if dataclasses.is_dataclass(payload):
        dumped = dataclasses.asdict(payload)
        if set(dumped) == {"params"} and isinstance(dumped["params"], dict):
            return dumped["params"]
        return dumped
    return payload if isinstance(payload, dict) else {}


def text_from_blocks(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for block in blocks:
        btype = block.get("type")
        if btype == "text":
            parts.append(str(block.get("text") or ""))
        elif btype == "image":
            parts.append(
                "[User sent an image attachment; if needed, ask them to upload it as a file reference.]"
            )
        else:
            parts.append(json.dumps(block, ensure_ascii=False))
    return "\n".join(part for part in parts if part).strip()


def input_text(turn_input: dict[str, Any]) -> str:
    blocks = turn_input.get("message", {}).get("content") or []
    if not isinstance(blocks, list):
        blocks = []
    return text_from_blocks(blocks) or "continue"


def _laminar_otel_endpoint() -> str:
    endpoint = (os.environ.get("CODEX_OTEL_LAMINAR_ENDPOINT") or "").strip()
    if endpoint:
        return endpoint
    base = (
        os.environ.get("CODEX_OTEL_LAMINAR_BASE_URL")
        or os.environ.get("LMNR_BASE_URL")
        or ""
    ).strip()
    if not base:
        return ""
    base = base.rstrip("/")
    if base.endswith("/v1/traces"):
        return base
    return f"{base}/v1/traces"


def laminar_otel_writes(
    trace_id: str | None,
    thread_key: str | None,
) -> list[tuple[str, Any]]:
    endpoint = _laminar_otel_endpoint()
    trace_id = (trace_id or os.environ.get("CENTAUR_TRACE_ID") or "").strip()
    if not endpoint or not trace_id:
        return []

    headers = {"x-trace-id": trace_id}
    thread_key = (thread_key or os.environ.get("CENTAUR_THREAD_KEY") or "").strip()
    if thread_key:
        headers["x-centaur-thread-key"] = thread_key
    api_key = (os.environ.get("LMNR_PROJECT_API_KEY") or "").strip()
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    environment = (
        os.environ.get("CODEX_OTEL_ENVIRONMENT")
        or os.environ.get("DEPLOY_ENV")
        or os.environ.get("ENVIRONMENT")
        or "dev"
    ).strip() or "dev"

    return [
        ("otel.environment", environment),
        ("otel.log_user_prompt", False),
        ("otel.trace_exporter.otlp-http.endpoint", endpoint),
        ("otel.trace_exporter.otlp-http.protocol", "binary"),
        ("otel.trace_exporter.otlp-http.headers", headers),
    ]


class CodexBridge:
    def __init__(self) -> None:
        self.inputs: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.codex: Any | None = None
        self.thread: Any | None = None
        self.thread_id: str | None = None
        self.active_turn: Any | None = None
        self.configured_otel_trace_id: str | None = None
        self.shutting_down = False

    async def configure_laminar_otel(
        self,
        trace_id: str | None,
        thread_key: str | None,
    ) -> None:
        trace_id = (trace_id or os.environ.get("CENTAUR_TRACE_ID") or "").strip()
        if not trace_id or self.configured_otel_trace_id == trace_id:
            return
        writes = laminar_otel_writes(trace_id, thread_key)
        if not writes:
            return
        assert self.codex is not None

        for key_path, value in writes:
            await self.codex._client.request(
                "config/value/write",
                {"keyPath": key_path, "value": value, "mergeStrategy": "upsert"},
                response_model=IgnoredResponse,
            )
        self.configured_otel_trace_id = trace_id

    async def start_or_resume_thread(self) -> str:
        if self.thread is not None and self.thread_id:
            return self.thread_id

        assert self.codex is not None
        from openai_codex import ApprovalMode

        resume = (
            os.environ.get("CODEX_CONTINUE_THREAD_ID")
            or os.environ.get("AMP_CONTINUE_THREAD_ID")
            or ""
        ).strip()
        if resume:
            self.thread = await self.codex.thread_resume(
                resume,
                approval_mode=ApprovalMode.deny_all,
                cwd=os.getcwd(),
            )
        else:
            self.thread = await self.codex.thread_start(
                approval_mode=ApprovalMode.deny_all,
                cwd=os.getcwd(),
            )
        self.thread_id = str(getattr(self.thread, "id", None) or resume)
        emit({"type": "thread.started", "thread_id": self.thread_id})
        return self.thread_id

    def emit_notification(self, notification: Any) -> bool:
        method = str(getattr(notification, "method", "") or "")
        params = _payload_dict(getattr(notification, "payload", {}))

        if method in {
            "turn/started",
            "item/started",
            "item/updated",
            "item/completed",
            "item/commandExecution/outputDelta",
            "item/agentMessage/delta",
            "item/fileChange/outputDelta",
            "item/fileChange/patchUpdated",
            "item/plan/delta",
            "item/reasoning/summaryTextDelta",
            "item/reasoning/summaryPartAdded",
            "item/reasoning/textDelta",
            "turn/plan/updated",
            "thread/goal/updated",
        }:
            payload = {"type": method.replace("/", "."), **params}
            if (
                method == "item/agentMessage/delta"
                and self.thread_id
                and "session_id" not in payload
                and "thread_id" not in payload
            ):
                payload["session_id"] = self.thread_id
            emit(payload)
            return False

        if method == "turn/completed":
            turn = params.get("turn") or {}
            emit(
                {
                    "type": "turn.completed",
                    "turn": turn,
                    "usage": params.get("usage") or turn.get("usage"),
                }
            )
            self.active_turn = None
            return True

        if method in {"turn/failed", "error"}:
            emit({"type": "turn.failed", "error": params.get("error") or params})
            self.active_turn = None
            return True

        return False

    async def drain_until_turn_done(self, turn: Any) -> None:
        stream = turn.stream()
        notification_task = asyncio.create_task(stream.__anext__())
        input_task = asyncio.create_task(self.inputs.get())
        try:
            while not self.shutting_down:
                done, _pending = await asyncio.wait(
                    {notification_task, input_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if notification_task in done:
                    try:
                        notification = notification_task.result()
                    except StopAsyncIteration:
                        return
                    if self.emit_notification(notification):
                        return
                    notification_task = asyncio.create_task(stream.__anext__())

                if input_task in done:
                    incoming = input_task.result()
                    if incoming is None:
                        self.shutting_down = True
                        return
                    await self.handle_input(incoming)
                    if self.active_turn is None:
                        return
                    input_task = asyncio.create_task(self.inputs.get())
        finally:
            notification_task.cancel()
            input_task.cancel()
            await asyncio.gather(notification_task, input_task, return_exceptions=True)
            await stream.aclose()

    async def handle_input(self, turn_input: dict[str, Any]) -> None:
        if turn_input.get("type") == "interrupt":
            await self.interrupt_active_turn()
            return
        if turn_input.get("type") != "user":
            return

        await self.configure_laminar_otel(
            turn_input.get("trace_id"),
            turn_input.get("thread_key"),
        )
        thread_id = await self.start_or_resume_thread()
        text = input_text(turn_input)
        stripped = text.strip()
        if stripped.startswith("/goal") and (goal := stripped[len("/goal") :].strip()):
            assert self.codex is not None

            await self.codex._client.request(
                "thread/goal/set",
                {"threadId": thread_id, "objective": goal},
                response_model=IgnoredResponse,
            )
            emit(
                {
                    "type": "assistant",
                    "session_id": thread_id,
                    "message": {"content": [{"type": "text", "text": "Goal set."}]},
                }
            )
            emit({"type": "turn.completed"})
            return

        from openai_codex import ApprovalMode, TextInput

        text_input = TextInput(text)
        if self.active_turn is not None or turn_input.get("steer"):
            try:
                if self.active_turn is None:
                    raise RuntimeError("no active turn to steer")
                await self.active_turn.steer(text_input)
                return
            except Exception:
                await self.interrupt_active_turn()

        assert self.thread is not None

        turn = await self.thread.turn(text_input, approval_mode=ApprovalMode.deny_all)
        self.active_turn = turn
        await self.drain_until_turn_done(turn)

    async def interrupt_active_turn(self) -> None:
        if self.active_turn is not None:
            try:
                await self.active_turn.interrupt()
            except Exception as exc:
                emit({"type": "error", "message": f"interrupt failed: {exc}"})
        self.active_turn = None

    def stop(self) -> None:
        self.shutting_down = True
        self.inputs.put_nowait(None)

    async def run(self) -> None:
        from openai_codex import AppServerConfig, AsyncCodex

        codex_bin = (
            os.environ.get("CODEX_APP_SERVER_BIN")
            or os.environ.get("CODEX_BIN")
            or shutil.which("codex")
        )
        config = AppServerConfig(
            codex_bin=codex_bin,
            config_overrides=(
                'sandbox_mode="danger-full-access"',
                'approval_policy="never"',
                "features.goals=true",
            ),
            cwd=os.getcwd(),
            client_name="centaur",
            client_title="Centaur",
            client_version="0.1.0",
            experimental_api=True,
        )

        async with AsyncCodex(config=config) as codex:
            self.codex = codex
            emit({"type": "system", "subtype": "wrapper_heartbeat", "phase": "startup"})

            stdin_task = asyncio.create_task(read_api_stdin(self.inputs))
            try:
                while not self.shutting_down:
                    item = await self.inputs.get()
                    if item is None:
                        break
                    try:
                        await self.handle_input(item)
                    except Exception as exc:
                        emit({"type": "error", "message": str(exc)})
                        emit({"type": "turn.failed", "error": {"message": str(exc)}})
            finally:
                stdin_task.cancel()
                await asyncio.gather(stdin_task, return_exceptions=True)
                await self.interrupt_active_turn()


async def read_api_stdin(inputs: asyncio.Queue[dict[str, Any] | None]) -> None:
    while True:
        raw = await asyncio.to_thread(sys.stdin.readline)
        if raw == "":
            break
        line = raw.strip()
        if not line:
            continue
        try:
            await inputs.put(json.loads(line))
        except json.JSONDecodeError:
            emit({"type": "error", "message": "invalid stdin JSON"})
    await inputs.put(None)


def install_signal_handlers(bridge: CodexBridge) -> None:
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, bridge.stop)
    loop.add_signal_handler(
        signal.SIGUSR1,
        lambda: asyncio.create_task(bridge.interrupt_active_turn()),
    )


async def async_main() -> None:
    bridge = CodexBridge()
    install_signal_handlers(bridge)
    await bridge.run()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
