"""Backend that returns key names as stub values for firewall injection.

In server mode, tools never see real secrets. They receive the key name
itself (e.g. ``secret("ALCHEMY_API_KEY")`` → ``"ALCHEMY_API_KEY"``).
The outbound HTTPS request carries this stub in a header, and the
firewall (mitmproxy) replaces it with the real secret before it leaves
the network.

Only keys that actually exist in the secrets service are stubbed.
Unknown keys return ``None`` so that caller-provided defaults are used.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request

from centaur_sdk.backends.base import SecretBackend

log = logging.getLogger(__name__)

_DEFAULT_URL = "http://firewall:8081"
_REFRESH_INTERVAL = 300  # seconds


class StubBackend(SecretBackend):
    """Return the key name itself as the value, but only for known secrets.

    On first use, fetches the list of available keys from the firewall
    sidecar (``/keys``). Keys not present in the secrets service return
    ``None``, allowing ``secret("CONFIG_VAL", default)`` to use the default.
    """

    def __init__(self, url: str | None = None):
        self._url = url or os.environ.get("SECRET_MANAGER_URL", _DEFAULT_URL)
        self._known_keys: set[str] = set()
        self._last_refresh: float = 0
        self._lock = threading.Lock()

    def _refresh_keys(self) -> None:
        now = time.monotonic()
        with self._lock:
            if now - self._last_refresh < _REFRESH_INTERVAL and self._known_keys:
                return
        try:
            req = urllib.request.Request(f"{self._url}/keys")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            keys = set(data.get("keys", []))
            with self._lock:
                self._known_keys = keys
                self._last_refresh = now
            log.info("stub backend refreshed %d known keys", len(keys))
        except Exception:
            log.debug("stub backend: could not fetch keys from %s", self._url)

    async def get(self, key: str) -> str | None:
        self._refresh_keys()
        with self._lock:
            if key in self._known_keys:
                return key
        return None

    async def list_keys(self) -> list[str]:
        self._refresh_keys()
        with self._lock:
            return sorted(self._known_keys)
