"""Minimal mock secret manager for auth pentest tests.

Serves secrets from environment variables over HTTP, matching the real
secret manager's API surface (/health, /secrets/{key}, /keys).
"""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRETS = {
    "UI_PASSWORD": os.environ.get("UI_PASSWORD", ""),
    "API_SECRET_KEY": os.environ.get("API_SECRET_KEY", ""),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok", "cached_keys": len(SECRETS)})
        elif self.path == "/keys":
            self._json(200, {"keys": sorted(SECRETS.keys()), "count": len(SECRETS)})
        elif self.path.startswith("/secrets/"):
            key = self.path.split("/secrets/", 1)[1]
            if key in SECRETS:
                self._json(200, {"value": SECRETS[key]})
            else:
                self._json(404, {"detail": "not found"})
        else:
            self._json(404, {"detail": "not found"})

    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass  # suppress request logs


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8100), Handler)
    print("Mock secret manager listening on :8100")
    server.serve_forever()
