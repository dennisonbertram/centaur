"""Composio tool — execute actions from 1000+ services via Composio's cloud API.

iron-proxy integration verified: the Composio Python SDK sends the API key as
an `x-api-key` header to `backend.composio.dev`, which matches the secret
declaration in pyproject.toml. In a production Centaur deployment, iron-proxy
will replace the placeholder value with the real credential on outbound
requests.
"""

from __future__ import annotations

import logging
import os
import time

from centaur_sdk import secret

log = logging.getLogger(__name__)

_DEFAULT_USER_ID = "centaur"

_ALLOWED_TOOLKITS: set[str] | None = None
_raw = os.environ.get("COMPOSIO_ALLOWED_TOOLKITS", "").strip()
if _raw:
    _ALLOWED_TOOLKITS = {t.strip().lower() for t in _raw.split(",") if t.strip()}

# Cache toolkit versions to avoid dangerously_skip_version_check.
# Maps toolkit slug -> (version, expiry_time).
_VERSION_CACHE: dict[str, tuple[str, float]] = {}
_VERSION_TTL = 3600  # 1 hour


def _toolkit_from_slug(tool_slug: str) -> str:
    return tool_slug.split("_")[0].lower() if "_" in tool_slug else tool_slug.lower()


def _check_toolkit_allowed(tool_slug: str) -> str | None:
    if _ALLOWED_TOOLKITS is None:
        return None
    toolkit = _toolkit_from_slug(tool_slug)
    if toolkit not in _ALLOWED_TOOLKITS:
        return f"Toolkit '{toolkit}' is not in the allowed list: {sorted(_ALLOWED_TOOLKITS)}"
    return None


def _extract_tools(raw: list) -> list[dict]:
    tools = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        fn = t.get("function", {})
        params = fn.get("parameters", {})
        tools.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "required_params": params.get("required", []),
        })
    return tools


class ComposioClient:
    """Bridge to Composio's tool execution platform."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or secret("COMPOSIO_API_KEY")
        self._composio = None

    def _get_client(self):
        if self._composio is None:
            from composio import Composio
            self._composio = Composio(api_key=self._api_key)
        return self._composio

    def _resolve_version(self, tool_slug: str, user_id: str) -> str | None:
        """Resolve the toolkit version for a tool slug, with caching."""
        toolkit = _toolkit_from_slug(tool_slug)
        now = time.monotonic()
        cached = _VERSION_CACHE.get(toolkit)
        if cached and cached[1] > now:
            return cached[0]
        try:
            c = self._get_client()
            raw = c.tools.get(user_id, toolkits=[toolkit])
            if isinstance(raw, list) and raw:
                t = raw[0]
                if isinstance(t, dict):
                    version = t.get("version") or t.get("toolkit_version")
                    if version:
                        _VERSION_CACHE[toolkit] = (version, now + _VERSION_TTL)
                        return version
        except Exception:
            pass
        return None

    def list_tools(self, toolkit: str, user_id: str = _DEFAULT_USER_ID) -> dict:
        """List available tools for a toolkit (e.g. 'github', 'gmail', 'slack', 'notion')."""
        if not toolkit or not toolkit.strip():
            return {"error": "toolkit is required", "successful": False}
        toolkit = toolkit.strip()
        if _ALLOWED_TOOLKITS is not None and toolkit.lower() not in _ALLOWED_TOOLKITS:
            return {"error": f"Toolkit '{toolkit}' is not allowed", "successful": False}
        try:
            c = self._get_client()
            raw = c.tools.get(user_id, toolkits=[toolkit])
            tools = _extract_tools(raw if isinstance(raw, list) else [])
            return {"toolkit": toolkit, "tools": tools, "count": len(tools)}
        except Exception as exc:
            log.warning("composio list_tools failed", exc_info=True)
            return {"error": str(exc), "successful": False}

    def search_tools(self, query: str, user_id: str = _DEFAULT_USER_ID) -> dict:
        """Search for tools across all toolkits by description."""
        if not query or not query.strip():
            return {"error": "query is required", "successful": False}
        try:
            c = self._get_client()
            raw = c.tools.get(user_id, search=query.strip())
            items = raw[:20] if isinstance(raw, list) else []
            tools = _extract_tools(items)
            if _ALLOWED_TOOLKITS is not None:
                tools = [t for t in tools if _toolkit_from_slug(t["name"]) in _ALLOWED_TOOLKITS]
            return {"query": query, "tools": tools, "count": len(tools)}
        except Exception as exc:
            log.warning("composio search_tools failed", exc_info=True)
            return {"error": str(exc), "successful": False}

    def execute(
        self,
        tool_slug: str,
        arguments: dict | None = None,
        user_id: str = _DEFAULT_USER_ID,
    ) -> dict:
        """Execute a Composio tool action.

        tool_slug examples: GITHUB_LIST_REPOS_FOR_USER, HACKERNEWS_GET_TOP_STORIES.
        Use get_tool_schema() to discover required arguments.
        """
        if not tool_slug or not tool_slug.strip():
            return {"error": "tool_slug is required", "successful": False}
        tool_slug = tool_slug.strip()
        blocked = _check_toolkit_allowed(tool_slug)
        if blocked:
            return {"error": blocked, "successful": False}
        try:
            c = self._get_client()
            # Try cached version first; fall back to skip if resolution fails.
            version = self._resolve_version(tool_slug, user_id)
            kwargs: dict = {
                "user_id": user_id,
                "arguments": arguments or {},
            }
            if version:
                kwargs["version"] = version
            else:
                kwargs["dangerously_skip_version_check"] = True
            result = c.tools.execute(tool_slug, **kwargs)
            if isinstance(result, dict):
                return {
                    "successful": result.get("successful", False),
                    "error": result.get("error"),
                    "data": result.get("data", {}),
                }
            return {
                "successful": getattr(result, "successful", False),
                "error": getattr(result, "error", None),
                "data": getattr(result, "data", {}),
            }
        except Exception as exc:
            log.warning("composio execute failed", exc_info=True)
            return {"error": str(exc), "successful": False}

    def get_tool_schema(self, tool_slug: str, user_id: str = _DEFAULT_USER_ID) -> dict:
        """Get the input/output schema for a specific tool."""
        if not tool_slug or not tool_slug.strip():
            return {"error": "tool_slug is required", "successful": False}
        tool_slug = tool_slug.strip()
        blocked = _check_toolkit_allowed(tool_slug)
        if blocked:
            return {"error": blocked, "successful": False}
        try:
            c = self._get_client()
            raw = c.tools.get(user_id, search=tool_slug)
            for t in raw if isinstance(raw, list) else []:
                if not isinstance(t, dict):
                    continue
                fn = t.get("function", {})
                if fn.get("name") == tool_slug:
                    return {
                        "successful": True,
                        "name": fn.get("name"),
                        "description": fn.get("description", ""),
                        "parameters": fn.get("parameters", {}),
                    }
            return {"error": f"Tool {tool_slug} not found", "successful": False}
        except Exception as exc:
            log.warning("composio get_tool_schema failed", exc_info=True)
            return {"error": str(exc), "successful": False}


def _client() -> ComposioClient:
    return ComposioClient()
