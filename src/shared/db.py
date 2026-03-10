from __future__ import annotations

from typing import Any

import asyncpg
import structlog

log = structlog.get_logger()


async def create_pool(database_url: str) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )
    assert pool is not None
    await _ensure_schema(pool)
    return pool


async def close_pool(pool: asyncpg.Pool) -> None:
    await pool.close()


async def execute(pool: asyncpg.Pool, query: str, *args: Any) -> str:
    return await pool.execute(query, *args)


async def fetch(pool: asyncpg.Pool, query: str, *args: Any) -> list[asyncpg.Record]:
    return await pool.fetch(query, *args)


async def fetchrow(pool: asyncpg.Pool, query: str, *args: Any) -> asyncpg.Record | None:
    return await pool.fetchrow(query, *args)


async def _drop_orphan_composite_type(conn: asyncpg.Connection, relation_name: str) -> None:
    """Drop leftover row-type if table was removed but type remains."""
    table_exists = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = current_schema()
              AND c.relname = $1
              AND c.relkind = 'r'
        )
        """,
        relation_name,
    )
    if table_exists:
        return

    type_exists = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = $1)",
        relation_name,
    )
    if type_exists:
        await conn.execute(f'DROP TYPE IF EXISTS "{relation_name}"')
        log.warning("dropped_orphan_composite_type", relation=relation_name)


async def _ensure_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await _drop_orphan_composite_type(conn, "agent_sessions")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    log.info("schema_ensured")
