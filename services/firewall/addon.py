"""Firewall addon — host-based credential injection + provider rewriting.

Intercepts ALL outgoing HTTPS requests from sandbox containers. For known
API hosts, unconditionally injects the appropriate credential header with
real secrets fetched on demand from the secret manager service.

Amp routes LLM calls through ampcode.com/api/provider/{provider}/... which
requires a paid plan. To bypass this, the firewall rewrites these requests
to go directly to the real API endpoint (e.g. api.anthropic.com) with the
correct credentials.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from mitmproxy import http

log = logging.getLogger("firewall")

SECRET_MANAGER_URL = os.environ.get("SECRET_MANAGER_URL", "http://secrets:8100")
CACHE_TTL = int(os.environ.get("FIREWALL_CACHE_TTL", "30"))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8081"))

BLOCKED_HOSTS: frozenset[str] = frozenset({
    "secrets",
    "169.254.169.254",
})

# Host → (secret_key, header_name, style)
# Styles: "raw"    → value is the secret itself
#         "bearer" → "Bearer {secret}"
#         "token"  → "token {secret}"
#         "basic"  → "Basic base64(x-access-token:{secret})"
_HOST_RULES: dict[str, tuple[str, str, str]] = {
    "api.anthropic.com": ("ANTHROPIC_API_KEY", "x-api-key", "raw"),
    "api.openai.com": ("OPENAI_API_KEY", "authorization", "bearer"),
    "ampcode.com": ("AMP_API_KEY", "authorization", "bearer"),
    "api.ampcode.com": ("AMP_API_KEY", "authorization", "bearer"),
    "api.github.com": ("GITHUB_TOKEN", "authorization", "token"),
    "github.com": ("GITHUB_TOKEN", "authorization", "basic"),
    "uploads.github.com": ("GITHUB_TOKEN", "authorization", "token"),
}

# Amp provider proxy rewriting: ampcode.com/api/provider/{provider}/...
# is rewritten to call the real API directly with the correct credentials.
# prefix_to_strip → (real_host, secret_key, header_name, style)
_PROVIDER_REWRITES: dict[str, tuple[str, str, str, str]] = {
    "/api/provider/anthropic/": ("api.anthropic.com", "ANTHROPIC_API_KEY", "x-api-key", "raw"),
    "/api/provider/openai/": ("api.openai.com", "OPENAI_API_KEY", "authorization", "bearer"),
}


def _format_header(secret: str, style: str) -> str:
    if style == "bearer":
        return f"Bearer {secret}"
    if style == "token":
        return f"token {secret}"
    if style == "basic":
        raw = f"x-access-token:{secret}"
        return f"Basic {base64.b64encode(raw.encode()).decode()}"
    return secret


class CredentialInjector:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[str | None, float]] = {}
        self._lock = threading.Lock()
        log.info("credential injector started (host rules: %s)", ", ".join(sorted(_HOST_RULES)))
        self._start_health_server()

    def _start_health_server(self) -> None:
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/health":
                    with parent._lock:
                        cached = sum(1 for v, _ in parent._cache.values() if v is not None)
                    body = json.dumps({"status": "ok", "secrets_cached": cached})
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body.encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, fmt: str, *args: object) -> None:
                pass

        def serve() -> None:
            server = HTTPServer(("0.0.0.0", HEALTH_PORT), Handler)
            server.serve_forever()

        threading.Thread(target=serve, daemon=True).start()

    def _get_secret(self, key: str) -> str | None:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached and (now - cached[1]) < CACHE_TTL:
                return cached[0]

        try:
            url = f"{SECRET_MANAGER_URL}/secrets/{urllib.parse.quote(key, safe='')}"
            with urllib.request.urlopen(url, timeout=3) as resp:
                val = json.loads(resp.read().decode()).get("value")
        except Exception:
            val = None

        with self._lock:
            self._cache[key] = (val, now)

        if val is None:
            log.warning("secret %s: not found in secret manager", key)
        return val

    def _try_provider_rewrite(self, flow: http.HTTPFlow, host: str) -> bool:
        """Rewrite amp provider proxy calls to go directly to the real API.

        Returns True if the request was rewritten.
        """
        if host not in ("ampcode.com", "api.ampcode.com"):
            return False

        path = flow.request.path
        for prefix, (real_host, secret_key, header_name, style) in _PROVIDER_REWRITES.items():
            if not path.startswith(prefix):
                continue

            secret = self._get_secret(secret_key)
            if secret is None:
                log.warning("provider rewrite: no secret for %s", secret_key)
                return False

            # Rewrite: /api/provider/anthropic/v1/messages → /v1/messages
            new_path = path[len(prefix) - 1:]  # keep the leading /
            flow.request.host = real_host
            flow.request.port = 443
            flow.request.scheme = "https"
            flow.request.path = new_path
            flow.request.headers["host"] = real_host
            flow.request.headers[header_name] = _format_header(secret, style)

            # Remove amp-specific auth header since we're going direct
            if header_name != "authorization" and "authorization" in flow.request.headers:
                del flow.request.headers["authorization"]

            log.info(
                "provider rewrite: %s%s → %s%s",
                host, path, real_host, new_path,
            )
            return True

        return False

    def request(self, flow: http.HTTPFlow) -> None:
        host = flow.request.pretty_host.lower().rstrip(".")

        if host in BLOCKED_HOSTS:
            flow.response = http.Response.make(
                403, b"Blocked by security policy", {"content-type": "text/plain"},
            )
            log.warning("blocked request to %s", host)
            return

        # Check for amp provider proxy rewrite first
        if self._try_provider_rewrite(flow, host):
            return

        rule = _HOST_RULES.get(host)
        if rule is None:
            return

        secret_key, header_name, style = rule
        secret = self._get_secret(secret_key)
        if secret is None:
            log.warning("no secret for %s (key=%s) — passing request unmodified", host, secret_key)
            return

        flow.request.headers[header_name] = _format_header(secret, style)


addons = [CredentialInjector()]
