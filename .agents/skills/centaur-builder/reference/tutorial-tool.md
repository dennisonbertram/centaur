# Tutorial: Building a Tool

End-to-end walkthrough: write a tool locally, test it on your machine, deploy it to Centaur, and verify it works.

We'll build a real tool that wraps the Hacker News API.

---

## Step 1: Create the files locally

Make a directory anywhere on your machine:

```bash
mkdir -p my-hackathon-tool/hackernews
cd my-hackathon-tool/hackernews
```

Create three files:

**`__init__.py`** — empty, just needs to exist:

```bash
touch __init__.py
```

**`client.py`** — your API client:

```python
"""Hacker News API client."""

import httpx


class HackerNewsClient:
    """Hacker News API client."""

    def top_stories(self, limit: int = 10) -> list[dict]:
        """Get the current top stories from Hacker News."""
        with httpx.Client() as client:
            ids = client.get("https://hacker-news.firebaseio.com/v0/topstories.json").json()
            stories = []
            for story_id in ids[:limit]:
                story = client.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                ).json()
                stories.append({
                    "title": story.get("title"),
                    "url": story.get("url"),
                    "score": story.get("score"),
                })
            return stories

    def get_item(self, item_id: int) -> dict:
        """Get a single item (story, comment, etc.) by ID."""
        with httpx.Client() as client:
            return client.get(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            ).json()


def _client() -> HackerNewsClient:
    return HackerNewsClient()
```

**`pyproject.toml`** — package metadata:

```toml
[project]
name = "hackernews"
description = "Hacker News API - top stories, items, and comments"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["httpx>=0.27.0"]

[tool.ai-v2]
module = "client.py"
```

---

## Step 2: Test it locally with Python

You don't need Centaur running to test your tool. Just call it directly:

```bash
# Install the dependency
pip3 install httpx

# Test from the parent directory (my-hackathon-tool/)
cd ..
python3 -c "
from hackernews.client import _client
client = _client()

# Test top_stories
stories = client.top_stories(limit=3)
for s in stories:
    print(f'{s[\"score\"]:>4}  {s[\"title\"]}')
    print(f'      {s[\"url\"]}')
    print()

# Test get_item
item = client.get_item(1)
print('Item 1:', item)
"
```

You should see real Hacker News stories printed. If something is broken, fix it and re-run — this is your fast local iteration loop.

### If your tool needs an API key

For local testing, just set the env var directly:

```bash
export MY_API_KEY="your-key-here"
python3 -c "
from my_tool.client import _client
client = _client()
print(client.search('test'))
"
```

The `secret()` function falls back to environment variables, so this works locally without 1Password.

---

## Step 3: Deploy to Centaur

Once it works locally, deploy it. Use the Centaur API to trigger an agent that commits your code:

```bash
export CENTAUR_API_KEY="aiv2_your_key_here"

# Read your files into variables
CLIENT_PY=$(cat hackernews/client.py)
PYPROJECT=$(cat hackernews/pyproject.toml)

# Use the helper script (or the raw spawn→message→execute flow)
# Tell the agent exactly what files to create and where
```

The simplest way — paste your code into a message to a Centaur agent:

```bash
THREAD_KEY="deploy-tool-$(date +%s)"

# Spawn
SPAWN=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/spawn \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"harness\":\"amp\"}")
AG=$(echo "$SPAWN" | python3 -c "import sys,json; print(json.load(sys.stdin)['assignment_generation'])")

# Build the message with your code
MSG="Add a new tool called 'hackernews' to paradigmxyz/centaur.

Create these files in tools/hackernews/:

__init__.py (empty)

client.py:
\`\`\`python
${CLIENT_PY}
\`\`\`

pyproject.toml:
\`\`\`toml
${PYPROJECT}
\`\`\`

Then open a PR and merge it."

# Send the message
curl -s -X POST https://svc-ai.dayno.xyz/agent/message \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"text\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$MSG")}]}"

# Execute
EXECUTE=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"harness\":\"amp\",\"delivery\":{\"platform\":\"dev\"}}")
EXECUTION_ID=$(echo "$EXECUTE" | python3 -c "import sys,json; print(json.load(sys.stdin)['execution_id'])")

# Stream — watch the agent create the branch, write files, open PR, merge
curl -s -N "https://svc-ai.dayno.xyz/agent/threads/${THREAD_KEY}/events?execution_id=${EXECUTION_ID}&after_event_id=0" \
  -H "X-Api-Key: $CENTAUR_API_KEY"
```

---

## Step 4: Verify it's live

After the agent merges the PR, the tool hot-reloads within seconds. Verify:

```bash
# Check it shows up in the tool list
curl -s https://svc-ai.dayno.xyz/tools/hackernews \
  -H "X-Api-Key: $CENTAUR_API_KEY" | python3 -m json.tool

# Call it
curl -s -X POST https://svc-ai.dayno.xyz/tools/hackernews/top_stories \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{"limit": 3}' | python3 -m json.tool
```

Now any Centaur agent (including in Slack) can use your tool.

---

## Step 5: Iterate

Found a bug? Want to add a method? Same flow:

1. Fix the code locally
2. Test with Python
3. Tell the agent: *"Update the hackernews tool in paradigmxyz/centaur — replace client.py with this: [paste]. Open PR and merge."*

---

## If your tool needs an API key

Two things are required:

1. **In your code**: use `secret("MY_API_KEY")` from `centaur_sdk.tool_sdk`
2. **In 1Password**: add the key to the **Paradigm AI Secrets & API Keys** vault
   - Item title = the exact env var name (e.g., `HACKERNEWS_API_KEY`)
   - Put the value in the `password` field

Centaur's secrets manager loads from 1Password automatically.

---

## Checklist

- [ ] `client.py` has a `_client()` factory function at the bottom
- [ ] `pyproject.toml` has `[tool.ai-v2]` with `module = "client.py"`
- [ ] Public methods have docstrings (they become the tool's documentation)
- [ ] Tested locally with Python — methods return expected data
- [ ] API keys (if any) use `secret("KEY")` and are in 1Password
- [ ] Deployed via agent and verified with `GET /tools/<name>`
