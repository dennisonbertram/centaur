"""Backend that chains multiple backends, returning the first hit."""

from __future__ import annotations

from secret_backends.base import SecretBackend


class CompositeBackend(SecretBackend):
    """Try each backend in order, returning the first non-``None`` result."""

    def __init__(self, backends: list[SecretBackend]) -> None:
        self._backends = list(backends)

    async def get(self, key: str) -> str | None:
        for backend in self._backends:
            value = await backend.get(key)
            if value is not None:
                return value
        return None

    async def list_keys(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for backend in self._backends:
            for key in await backend.list_keys():
                if key not in seen:
                    seen.add(key)
                    result.append(key)
        return result
