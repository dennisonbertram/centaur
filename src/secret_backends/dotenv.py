"""Backend that reads secrets from ``.env`` files."""

from __future__ import annotations

from pathlib import Path

from secret_backends.base import SecretBackend


class DotEnvBackend(SecretBackend):
    """Read key=value pairs from a ``.env`` file.

    The file is parsed once on construction; call :meth:`reload` to re-read.
    """

    def __init__(self, path: str | Path = ".env") -> None:
        self._path = Path(path)
        self._data: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        """Re-read the ``.env`` file."""
        data: dict[str, str] = {}
        if not self._path.is_file():
            self._data = data
            return
        for line in self._path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key:
                data[key] = value
        self._data = data

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def list_keys(self) -> list[str]:
        return list(self._data.keys())
