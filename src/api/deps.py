from __future__ import annotations

import secrets
from typing import Annotated

import asyncpg
from fastapi import Depends, Header, HTTPException, Request
from openai import AsyncOpenAI

from shared.config import settings

_DOCKER_PREFIXES = ("172.", "192.168.", "10.", "127.")


async def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


async def get_embedding_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> EmbeddingService:
    return EmbeddingService(pool=pool)


async def verify_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header()] = None,
) -> str:
    # Docker network is trusted — only nginx is exposed to the host.
    client_ip = request.client.host if request.client else ""
    if client_ip.startswith(_DOCKER_PREFIXES):
        return "docker-bypass"


    if not settings.api_secret_key:
        raise HTTPException(status_code=500, detail="API key not configured")

    token = x_api_key
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]

    if not token or not secrets.compare_digest(token, settings.api_secret_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return token


async def verify_ui_or_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header()] = None,
) -> str:
    """Accept either nginx-forwarded auth (X-Forwarded-User) or an API key.

    When the request comes through nginx with a valid session cookie, nginx
    sets ``X-Forwarded-User`` via ``auth_request``.  To swap to Okta / SSO,
    replace the auth service container — this code stays the same.
    """
    if request.headers.get("x-forwarded-user"):
        return "nginx"
    return await verify_api_key(request, x_api_key)


class EmbeddingService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def embed(self, text: str) -> list[float]:
        resp = await self.client.embeddings.create(
            input=text,
            model="text-embedding-3-small",
        )
        return resp.data[0].embedding
