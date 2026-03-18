"""SessionManager — single owner of container session lifecycle.

Façade that delegates to agent.py, warm_pool.py, and the sandbox backend.
Routers and app lifespan should eventually import only from here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import structlog

from api.agent import (
    get_or_spawn,
    get_status,
    inject_stdin,
    reconcile_tick,
    stop_session,
    stream_connect,
    stream_reconnect,
)
from api.sandbox.base import SandboxSession
from api.warm_pool import (
    pool_status,
    start_replenish_loop,
    stop_replenish_loop,
)

log = structlog.get_logger()


class SessionManager:
    """Single owner of container session lifecycle.

    Delegates to internal collaborators:
    - agent.py: session CRUD, streaming, flush pipeline
    - warm_pool.py: pool inventory, replenish, claim
    - sandbox backend: container operations
    """

    async def get_or_create(
        self,
        thread_key: str,
        harness: str = "amp",
        *,
        engine: str | None = None,
    ) -> SandboxSession:
        """Get existing session or create a new one (warm pool → cold spawn)."""
        return await get_or_spawn(thread_key, harness, engine=engine)

    async def inject(
        self,
        session: SandboxSession,
        message: str | list,
        *,
        platform: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Flush pending messages + write to stdin."""
        return await inject_stdin(session, message, platform=platform, user_id=user_id)

    async def connect(
        self,
        session: SandboxSession,
        *,
        platform: str | None = None,
    ) -> AsyncIterator[dict]:
        """Attach to sandbox stdout and return persistent SSE wire."""
        return stream_connect(session, platform=platform)

    async def reconnect(
        self,
        session: SandboxSession,
        *,
        skip_done_count: int = 0,
    ) -> AsyncIterator[dict]:
        """Re-attach to running sandbox stdout without sending a turn."""
        return stream_reconnect(session, skip_done_count=skip_done_count)

    async def stop(self, thread_key: str) -> bool:
        """Stop sandbox and update DB."""
        return await stop_session(thread_key)

    async def status(self, thread_key: str) -> dict[str, Any]:
        """Check session/sandbox status."""
        return await get_status(thread_key)

    async def reconcile(self) -> None:
        """Run one reconciliation tick."""
        await reconcile_tick()

    def pool_info(self) -> dict:
        """Return warm pool diagnostics."""
        return pool_status()

    async def start(self) -> None:
        """Start background tasks (pool replenish)."""
        await start_replenish_loop()
        log.info("session_manager_started")

    async def shutdown(self) -> None:
        """Stop background tasks (leave warm containers alive)."""
        await stop_replenish_loop()
        log.info("session_manager_stopped")
