# Plugins

Drop plugin directories here. Each plugin needs:

```
plugins/
  my-plugin/
    manifest.json    # {"name": "my-plugin", "description": "...", "module": "tools.py"}
    .env             # PLUGIN_SCOPED_SECRET=value (gitignored)
    tools.py         # async functions decorated with @plugin_tool
```

## Writing a plugin

```python
# tools.py
from ai_v2.plugin_sdk import plugin_tool, secret

@plugin_tool()
async def my_search(query: str, limit: int = 10) -> dict:
    """Search something."""
    token = secret("MY_API_TOKEN")
    # ... use token, return results ...
    return {"results": [...]}
```

## Secrets

Each plugin's `.env` is loaded into an isolated context. Use `secret("KEY")` to access.
Never use `os.environ` — plugin secrets are scoped to avoid leakage.

## Profiles

Set `ACTIVE_PROFILE=research` to only load plugins listed in `profiles/research.json`:

```json
{"plugins": ["slack", "linear", "gsuite"]}
```

If not set, all discovered plugins are loaded.
