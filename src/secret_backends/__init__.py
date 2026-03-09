"""Pluggable secret backend system.

Public API:
    - ``get_backend()`` / ``configure()`` — access the active backend
    - ``SecretBackend`` — ABC for custom backends
    - ``StubBackend`` — server-mode default (returns key names as stubs)
    - ``EnvBackend`` / ``DotEnvBackend`` — CLI-only (banned in server code; see pyproject.toml)
    - ``HttpBackend`` / ``CompositeBackend`` — utility backends
"""

from __future__ import annotations

from secret_backends.base import SecretBackend
from secret_backends.composite import CompositeBackend
from secret_backends.dotenv import DotEnvBackend
from secret_backends.env import EnvBackend
from secret_backends.http import HttpBackend
from secret_backends.registry import auto_configure, configure, get_backend
from secret_backends.stub import StubBackend

__all__ = [
    "CompositeBackend",
    "DotEnvBackend",
    "EnvBackend",
    "HttpBackend",
    "SecretBackend",
    "StubBackend",
    "auto_configure",
    "configure",
    "get_backend",
]
