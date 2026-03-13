"""Agent router — execute/stop/status/reconnect."""

from __future__ import annotations

import asyncio
import json as _json
import time as _time
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Any

from pydantic import BaseModel

from api.agent import (
    claim_for_delivery,
    get_or_spawn,
    get_status,
    list_undelivered,
    mark_delivered,
    stop_session,
    stream_exec,
    stream_reconnect,
)
from api.deps import require_scope, verify_api_key
from api.warm_pool import pool_status
from api.warm_pool import replenish as replenish_pool

log = structlog.get_logger()

SSE_KEEPALIVE_INTERVAL = 30  # seconds


async def _sse_with_keepalive(source: AsyncIterator[str]) -> AsyncIterator[str]:
    """Wrap an SSE source with periodic keepalive comments.

    Sends ``: keepalive\\n\\n`` every SSE_KEEPALIVE_INTERVAL seconds when the
    underlying source is silent. This prevents proxies and HTTP clients from
    treating the connection as dead during long-running tool calls (e.g. oracle).
    """
    aiter = source.__aiter__()
    while True:
        try:
            line = await asyncio.wait_for(
                aiter.__anext__(), timeout=SSE_KEEPALIVE_INTERVAL
            )
            yield f"data: {line}\n\n"
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"
        except StopAsyncIteration:
            break
    yield "data: [DONE]\n\n"


router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(verify_api_key)],
)


class Attachment(BaseModel):
    name: str
    mime_type: str
    data: str  # base64-encoded file bytes


class ExecuteRequest(BaseModel):
    thread_key: str
    message: str | list[Any] = ""
    harness: str = "amp"
    engine: str | None = None
    platform: str | None = None
    user_id: str | None = None
    attachments: list[Attachment] | None = None


@router.post("/execute", dependencies=[Depends(require_scope("agent:execute"))])
async def execute(request: Request):
    body = await request.json()
    thread_key = body.get("thread_key")
    if not thread_key:
        raise HTTPException(status_code=422, detail="thread_key is required")

    harness = body.get("harness", "amp")
    engine = body.get("engine")
    platform = body.get("platform")
    user_id = body.get("user_id")
    message = body.get("message", "")
    attachments = body.get("attachments")

    if attachments:
        log.info(
            "attachments_received",
            thread_key=thread_key,
            count=len(attachments),
            names=[a["name"] for a in attachments],
        )

    session = await get_or_spawn(thread_key, harness, engine=engine)

    return StreamingResponse(
        _sse_with_keepalive(
            stream_exec(
                session,
                message,
                platform=platform,
                user_id=user_id,
            )
        ),
        media_type="text/event-stream",
    )


@router.post("/messages", dependencies=[Depends(require_scope("agent:execute"))])
async def post_messages(request: Request):
    """Buffer messages into chat_messages for a thread."""
    body = await request.json()
    thread_key = body.get("thread_key")
    if not thread_key:
        raise HTTPException(status_code=422, detail="thread_key is required")

    # Normalize: single message or batch
    raw_messages = body.get("messages")
    if raw_messages is None:
        # Single message request
        raw_messages = [{
            "role": body.get("role", "user"),
            "parts": body.get("parts", []),
            "user_id": body.get("user_id"),
            "metadata": body.get("metadata"),
        }]

    pool = request.app.state.db_pool
    inserted = 0
    for msg in raw_messages:
        parts = msg.get("parts", [])
        role = msg.get("role", "user")
        user_id = msg.get("user_id")
        metadata = msg.get("metadata") or {}

        # Generate deterministic ID from thread_key + slack_ts or timestamp
        slack_ts = metadata.get("slack_ts", "")
        if slack_ts:
            msg_id = f"{thread_key}-{slack_ts}"
        else:
            msg_id = f"{thread_key}-{int(_time.time() * 1000000)}"

        result = await pool.execute(
            "INSERT INTO chat_messages (id, thread_key, role, parts, user_id, metadata) "
            "VALUES ($1, $2, $3, $4::jsonb, $5, $6::jsonb) "
            "ON CONFLICT (id) DO NOTHING",
            msg_id,
            thread_key,
            role,
            _json.dumps(parts),
            user_id,
            _json.dumps(metadata),
        )
        if "INSERT 0 1" in result:
            inserted += 1

    log.info("message_buffered", thread_key=thread_key, message_count=len(raw_messages), inserted=inserted)
    return {"ok": True, "inserted": inserted}


@router.get("/messages", dependencies=[Depends(require_scope("agent:execute"))])
async def get_messages(request: Request, thread_key: str, cursor: str | None = None, limit: int = 50):
    """Paginated chat_messages for a thread."""
    pool = request.app.state.db_pool
    limit = min(limit, 200)

    if cursor:
        rows = await pool.fetch(
            "SELECT id, role, parts, user_id, metadata, created_at "
            "FROM chat_messages WHERE thread_key = $1 "
            "AND created_at > (SELECT created_at FROM chat_messages WHERE id = $2) "
            "ORDER BY created_at LIMIT $3",
            thread_key,
            cursor,
            limit + 1,
        )
    else:
        rows = await pool.fetch(
            "SELECT id, role, parts, user_id, metadata, created_at "
            "FROM chat_messages WHERE thread_key = $1 "
            "ORDER BY created_at LIMIT $2",
            thread_key,
            limit + 1,
        )

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    messages = []
    last_id = None
    for row in rows:
        last_id = row["id"]
        messages.append({
            "id": row["id"],
            "role": row["role"],
            "parts": row["parts"],
            "user_id": row["user_id"],
            "metadata": row["metadata"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        })

    return {
        "messages": messages,
        "cursor": last_id if has_more else None,
        "has_more": has_more,
    }


class ReconnectRequest(BaseModel):
    thread_key: str
    harness: str = "amp"
    engine: str | None = None
    skip_done_count: int = 0


@router.post("/reconnect", dependencies=[Depends(require_scope("agent:execute"))])
async def reconnect(req: ReconnectRequest):
    """Re-attach to a running container's stdout without sending a new turn.

    Used by the slackbot to recover an in-progress stream after an API restart.
    Returns 404 if no running session exists for this thread.
    """
    session = await get_or_spawn(req.thread_key, req.harness, engine=req.engine)

    return StreamingResponse(
        _sse_with_keepalive(
            stream_reconnect(session, skip_done_count=req.skip_done_count)
        ),
        media_type="text/event-stream",
    )


class StopRequest(BaseModel):
    thread_key: str


@router.post("/stop", dependencies=[Depends(require_scope("agent:stop"))])
async def stop(req: StopRequest):
    ok = await stop_session(req.thread_key)
    return {"ok": ok}


@router.get("/status", dependencies=[Depends(require_scope("agent:status"))])
async def status(request: Request, key: str):
    result = await get_status(key)
    # Add pending message count
    try:
        pool = request.app.state.db_pool
        session_row = await pool.fetchrow(
            "SELECT last_delivered_id FROM sandbox_sessions WHERE thread_key = $1", key
        )
        if session_row:
            last_id = session_row["last_delivered_id"]
            if last_id is None:
                count_row = await pool.fetchrow(
                    "SELECT COUNT(*) as cnt FROM chat_messages WHERE thread_key = $1", key
                )
            else:
                count_row = await pool.fetchrow(
                    "SELECT COUNT(*) as cnt FROM chat_messages WHERE thread_key = $1 "
                    "AND created_at > (SELECT created_at FROM chat_messages WHERE id = $2)",
                    key, last_id,
                )
            result["pending_messages"] = count_row["cnt"] if count_row else 0
        else:
            # No session yet — count all messages for this thread
            count_row = await pool.fetchrow(
                "SELECT COUNT(*) as cnt FROM chat_messages WHERE thread_key = $1", key
            )
            result["pending_messages"] = count_row["cnt"] if count_row else 0
    except Exception:
        pass
    return result


@router.get("/pool", dependencies=[Depends(require_scope("admin"))])
async def pool():
    """Return warm pool diagnostics."""
    return pool_status()


@router.post("/pool/replenish", dependencies=[Depends(require_scope("admin"))])
async def pool_replenish():
    """Manually trigger pool replenishment."""
    spawned = await replenish_pool()
    return {"spawned": spawned, **pool_status()}


@router.get("/orphaned", dependencies=[Depends(require_scope("agent:status"))])
async def list_orphaned(max_age_s: int = 300):
    """List threads that completed but may not have been delivered."""
    return await list_undelivered(max_age_s)


class MarkDeliveredRequest(BaseModel):
    thread_key: str


@router.post("/claim-delivery", dependencies=[Depends(require_scope("agent:execute"))])
async def claim_delivery_endpoint(req: MarkDeliveredRequest):
    """Atomically claim an idle session for delivery. Returns claimed=true if won the race."""
    claimed = await claim_for_delivery(req.thread_key)
    return {"claimed": claimed}


@router.post("/mark-delivered", dependencies=[Depends(require_scope("agent:execute"))])
async def mark_delivered_endpoint(req: MarkDeliveredRequest):
    """Mark a thread as delivered so it won't appear in orphan checks."""
    await mark_delivered(req.thread_key)
    return {"ok": True}
