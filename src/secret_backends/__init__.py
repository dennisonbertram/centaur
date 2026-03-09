"""Pluggable secret backend system.

Public API:
    - ``get_backend()`` / ``configure()`` — access the active backend
    - ``SecretBackend`` — ABC for custom backends
    - ``EnvBackend`` / ``DotEnvBackend`` / ``HttpBackend`` / ``CompositeBackend`` — built-in backends
"""

from __future__ import annotations

from secret_backends.base import SecretBackend
from secret_backends.composite import CompositeBackend
from secret_backends.dotenv import DotEnvBackend
from secret_backends.env import EnvBackend
from secret_backends.http import HttpBackend
from secret_backends.registry import auto_configure, configure, get_backend

__all__ = [
    "CompositeBackend",
    "DotEnvBackend",
    "EnvBackend",
    "HttpBackend",
    "SecretBackend",
    "auto_configure",
    "configure",
    "get_backend",
]
