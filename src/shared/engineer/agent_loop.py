from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from shared.engineer.loop_guards import GuardrailStopError, LoopGuardState
from shared.engineer.tool_protocol import (
    build_tool_result_blocks,
    extract_tool_uses,
    to_assistant_blocks,
    tool_signature,
)


class AgentLoopError(RuntimeError):
    pass


@dataclass
class AgentLoopResult:
    text: str
    turns: int
    tool_calls: int
    stop_reason: str


def _extract_text(content_blocks: list[Any]) -> str:
    parts: list[str] = []
    for block in content_blocks:
        if getattr(block, "type", "") == "text":
            parts.append(getattr(block, "text", ""))
    return "".join(parts).strip()


def _truncate(text: str, max_chars: int = 30000) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return f"{text[:half]}\n\n...truncated...\n\n{text[-half:]}"


async def run_agent_loop(
    *,
    api_key: str,
    model: str,
    max_tokens: int,
    system_prompt: str,
    user_prompt: str,
    tools: list[dict[str, Any]],
    execute_tool: Callable[[str, dict[str, Any]], Awaitable[str]] | None,
    guard_state: LoopGuardState,
    effort: str = "max",
) -> AgentLoopResult:
    try:
        from anthropic import AsyncAnthropic
    except Exception as exc:  # pragma: no cover
        raise AgentLoopError("anthropic package is required for engineer loop") from exc

    if not api_key:
        raise AgentLoopError("Missing ANTHROPIC_API_KEY")

    client = AsyncAnthropic(api_key=api_key)
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    last_stop_reason = "unknown"

    create_kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": effort},
    }
    if tools:
        create_kwargs["tools"] = tools

    while True:
        try:
            guard_state.check_turn()
        except GuardrailStopError as exc:
            raise AgentLoopError(str(exc)) from exc

        async with client.messages.stream(
            **create_kwargs,
            messages=cast(Any, messages),
        ) as stream:
            response = await stream.get_final_message()

        last_stop_reason = str(getattr(response, "stop_reason", "unknown"))
        content_blocks = list(getattr(response, "content", []))
        tool_calls = extract_tool_uses(content_blocks)

        if tool_calls:
            if execute_tool is None:
                raise AgentLoopError("Model requested tools but no executor was provided")

            messages.append({"role": "assistant", "content": to_assistant_blocks(content_blocks)})

            async def _exec_one(call: dict[str, Any]) -> tuple[str, str]:
                signature = tool_signature(call["name"], call["input"])
                try:
                    guard_state.add_tool_call(signature)
                    output = await execute_tool(call["name"], call["input"])
                    guard_state.mark_tool_success()
                except Exception as exc:
                    guard_state.mark_tool_failure()
                    output = f"Tool error: {exc}"
                return (call["id"], _truncate(output))

            tool_results = await asyncio.gather(*[_exec_one(c) for c in tool_calls])

            messages.append(
                {"role": "user", "content": build_tool_result_blocks(list(tool_results))}
            )
            continue

        text = _extract_text(content_blocks)
        return AgentLoopResult(
            text=text,
            turns=guard_state.turns,
            tool_calls=guard_state.tool_calls,
            stop_reason=last_stop_reason,
        )
