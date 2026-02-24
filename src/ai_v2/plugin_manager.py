"""Plugin discovery, loading, and registration."""

from __future__ import annotations

import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, get_type_hints

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

import structlog
from fastapi import APIRouter
from pydantic import create_model

from .plugin_sdk import PluginContext, reset_plugin_context, set_plugin_context

log = structlog.get_logger()


class LoadedTool:
    def __init__(self, plugin_name: str, tool_name: str, fn: Callable, ctx: PluginContext):
        self.plugin_name = plugin_name
        self.tool_name = tool_name
        self.fn = fn
        self.ctx = ctx

    @property
    def qualified_name(self) -> str:
        return f"{self.plugin_name}.{self.tool_name}"


class LoadedPlugin:
    def __init__(self, name: str, description: str, ctx: PluginContext, tools: list[LoadedTool]):
        self.name = name
        self.description = description
        self.ctx = ctx
        self.tools = tools


def _install_deps(deps: list[str]) -> None:
    """Install plugin dependencies into the current environment."""
    if not deps:
        return
    uv = shutil.which("uv")
    if uv:
        cmd = [uv, "pip", "install", "--quiet", *deps]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--quiet", *deps]
    log.info("installing_plugin_deps", deps=deps)
    subprocess.run(cmd, check=True, capture_output=True)


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. Ignores comments and blank lines."""
    secrets: dict[str, str] = {}
    if not path.exists():
        return secrets
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        secrets[k.strip()] = v.strip()
    return secrets


class PluginManager:
    def __init__(
        self,
        plugins_dir: Path,
        profiles_dir: Path | None = None,
        root_env_path: Path | None = None,
    ):
        self.plugins_dir = plugins_dir
        self.profiles_dir = profiles_dir
        self.plugins: dict[str, LoadedPlugin] = {}
        # Load root .env once — all plugins inherit these secrets
        self._root_secrets: dict[str, str] = {}
        if root_env_path is None:
            # Default: .env at the repo root (parent of plugins_dir)
            root_env_path = plugins_dir.parent / ".env"
        self._root_secrets = _load_env_file(root_env_path)

    def _get_enabled_plugins(self, profile: str | None) -> set[str] | None:
        """Return set of enabled plugin names, or None for all."""
        if not profile or not self.profiles_dir:
            return None
        profile_path = self.profiles_dir / f"{profile}.json"
        if not profile_path.exists():
            log.warning("profile_not_found", profile=profile)
            return None
        data = json.loads(profile_path.read_text())
        return set(data.get("plugins", []))

    def _collect_plugins(
        self, enabled: set[str] | None
    ) -> list[tuple[Path, dict]]:
        """Read pyproject.toml from each plugin dir and filter by profile."""
        plugins = []
        for plugin_dir in sorted(self.plugins_dir.iterdir()):
            if not plugin_dir.is_dir() or plugin_dir.name.startswith((".", "_")):
                continue

            pyproject_path = plugin_dir / "pyproject.toml"
            if not pyproject_path.exists():
                continue

            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)

            project = pyproject.get("project", {})
            plugin_conf = pyproject.get("tool", {}).get("ai-v2-plugin", {})

            # Use directory name as the plugin name for profiles
            name = plugin_dir.name
            if enabled is not None and name not in enabled:
                log.debug("plugin_skipped_by_profile", plugin=name)
                continue

            meta = {
                "name": name,
                "description": project.get("description", ""),
                "dependencies": project.get("dependencies", []),
                "module": plugin_conf.get("module", "tools.py"),
            }
            plugins.append((plugin_dir, meta))
        return plugins

    def discover(self, profile: str | None = None) -> list[LoadedPlugin]:
        """Discover and load all plugins."""
        if not self.plugins_dir.exists():
            log.info("plugins_dir_missing", path=str(self.plugins_dir))
            return []

        enabled = self._get_enabled_plugins(profile)
        plugin_entries = self._collect_plugins(enabled)

        # Collect all dependencies across enabled plugins and install in one shot
        all_deps: list[str] = []
        for _, meta in plugin_entries:
            all_deps.extend(meta.get("dependencies", []))
        if all_deps:
            try:
                _install_deps(list(set(all_deps)))
            except Exception:
                log.exception("plugin_deps_install_failed", deps=all_deps)

        # Now load each plugin
        loaded = []
        for plugin_dir, meta in plugin_entries:
            try:
                plugin = self._load_plugin(plugin_dir, meta)
                if plugin:
                    loaded.append(plugin)
            except Exception:
                log.exception("plugin_load_failed", plugin=meta.get("name", plugin_dir.name))

        self.plugins = {p.name: p for p in loaded}
        return loaded

    def _load_plugin(self, plugin_dir: Path, manifest: dict) -> LoadedPlugin | None:
        name = manifest["name"]

        # Build secrets: root .env (base) → plugin .env (override)
        secrets: dict[str, str] = dict(self._root_secrets)
        plugin_secrets = _load_env_file(plugin_dir / ".env")
        secrets.update(plugin_secrets)

        ctx = PluginContext(name=name, secrets=secrets)

        # Register the plugin dir as a package so relative imports work
        pkg_name = f"ai_v2.plugins_runtime.{name}"
        init_path = plugin_dir / "__init__.py"
        if init_path.exists():
            pkg_spec = importlib.util.spec_from_file_location(
                pkg_name, init_path,
                submodule_search_locations=[str(plugin_dir)],
            )
            if pkg_spec and pkg_spec.loader:
                pkg_mod = importlib.util.module_from_spec(pkg_spec)
                sys.modules[pkg_name] = pkg_mod
                pkg_spec.loader.exec_module(pkg_mod)
        else:
            # Create a virtual package
            import types
            pkg_mod = types.ModuleType(pkg_name)
            pkg_mod.__path__ = [str(plugin_dir)]  # type: ignore[attr-defined]
            sys.modules[pkg_name] = pkg_mod

        # Ensure parent namespace exists
        if "ai_v2.plugins_runtime" not in sys.modules:
            import types as _t
            ns = _t.ModuleType("ai_v2.plugins_runtime")
            ns.__path__ = []  # type: ignore[attr-defined]
            sys.modules["ai_v2.plugins_runtime"] = ns

        # Import the tools module
        module_file = manifest.get("module", "tools.py")
        module_path = plugin_dir / module_file
        if not module_path.exists():
            log.warning("plugin_module_missing", plugin=name, module=module_file)
            return None

        mod_name = f"{pkg_name}.tools"
        spec = importlib.util.spec_from_file_location(mod_name, module_path)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        module.__package__ = pkg_name  # type: ignore[attr-defined]
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)

        # Collect tools
        tools: list[LoadedTool] = []
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if callable(obj) and hasattr(obj, "__plugin_tool__"):
                tool_name = obj.__plugin_tool__
                tools.append(LoadedTool(name, tool_name, obj, ctx))

        description = manifest.get("description", "")
        plugin = LoadedPlugin(name, description, ctx, tools)
        log.info(
            "plugin_loaded",
            plugin=name,
            tools=[t.tool_name for t in tools],
        )
        return plugin

    def register_mcp_tools(self, mcp: Any) -> int:
        """Register all loaded plugin tools as MCP tools."""
        count = 0
        for plugin in self.plugins.values():
            for tool in plugin.tools:
                _register_mcp_tool(mcp, tool)
                count += 1
        log.info("mcp_plugin_tools_registered", count=count)
        return count

    def create_rest_router(self) -> APIRouter:
        """Create a FastAPI router with all plugin tools as POST endpoints."""
        from .deps import verify_api_key

        router = APIRouter(
            prefix="/plugins",
            dependencies=[__import__("fastapi").Depends(verify_api_key)],
        )

        for plugin in self.plugins.values():
            for tool in plugin.tools:
                _register_rest_endpoint(router, tool)

        # List endpoint
        @router.get("")
        async def list_plugins() -> dict:
            return {
                name: {
                    "description": p.description,
                    "tools": [t.tool_name for t in p.tools],
                }
                for name, p in self.plugins.items()
            }

        return router


def _make_wrapper(tool: LoadedTool) -> Callable:
    """Wrap a plugin tool function to inject context and handle errors."""

    async def wrapper(**kwargs: Any) -> str:
        token = set_plugin_context(tool.ctx)
        try:
            result = await tool.fn(**kwargs)
            if isinstance(result, str):
                return result
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "plugin": tool.plugin_name,
                "tool": tool.tool_name,
            })
        finally:
            reset_plugin_context(token)

    # Preserve original signature for schema generation
    wrapper.__name__ = tool.qualified_name.replace(".", "_")
    wrapper.__doc__ = tool.fn.__doc__ or f"{tool.plugin_name} — {tool.tool_name}"
    wrapper.__signature__ = inspect.signature(tool.fn)  # type: ignore[attr-defined]
    wrapper.__annotations__ = get_type_hints(tool.fn)
    return wrapper


def _register_mcp_tool(mcp: Any, tool: LoadedTool) -> None:
    """Register a single plugin tool as an MCP tool."""
    wrapper = _make_wrapper(tool)
    # FastMCP uses the function name as the tool name
    wrapper.__name__ = tool.qualified_name.replace(".", "_")
    mcp.tool(name=tool.qualified_name)(wrapper)


def _register_rest_endpoint(router: APIRouter, tool: LoadedTool) -> None:
    """Register a single plugin tool as a REST POST endpoint."""
    sig = inspect.signature(tool.fn)
    hints = get_type_hints(tool.fn)

    # Build Pydantic model from function signature
    fields: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        param_type = hints.get(param_name, Any)
        if param.default is inspect.Parameter.empty:
            fields[param_name] = (param_type, ...)
        else:
            fields[param_name] = (param_type, param.default)

    model_name = f"{tool.plugin_name}_{tool.tool_name}_Input"
    InputModel = create_model(model_name, **fields)

    wrapper = _make_wrapper(tool)

    async def endpoint(body: InputModel) -> dict:  # type: ignore[valid-type]
        result = await wrapper(**body.model_dump())
        return {"plugin": tool.plugin_name, "tool": tool.tool_name, "result": result}

    endpoint.__name__ = f"{tool.plugin_name}_{tool.tool_name}"
    router.post(
        f"/{tool.plugin_name}/{tool.tool_name}",
        name=tool.qualified_name,
        summary=tool.fn.__doc__ or tool.tool_name,
    )(endpoint)
