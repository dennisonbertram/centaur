"""Sandbox backend registry — select and configure the active backend."""

from __future__ import annotations

import os

from api.sandbox.base import SandboxBackend

_backend: SandboxBackend | None = None


def get_backend() -> SandboxBackend:
    """Get the configured sandbox backend. Auto-configures on first call."""
    global _backend
    if _backend is None:
        _backend = auto_configure()
    return _backend


def configure(backend: SandboxBackend) -> None:
    """Set the sandbox backend explicitly."""
    global _backend
    _backend = backend


def auto_configure() -> SandboxBackend:
    """Auto-detect which backend to use based on environment."""
    backend_name = os.getenv("SANDBOX_BACKEND", "docker")
    if backend_name == "docker":
        from api.sandbox.docker import DockerSandboxBackend

        return DockerSandboxBackend()
    raise ValueError(f"Unknown sandbox backend: {backend_name}")
