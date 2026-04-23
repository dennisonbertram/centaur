# Centaur Hackathon Guide

Welcome! This guide gets you from zero to building and deploying things on Centaur. No engineering background required — if you can copy-paste a command, you're good.

---

## What You Need

1. **Your API key** — find it in the [hackathon spreadsheet](https://docs.google.com/spreadsheets/d/15Zu4OVXYq640YCeQouLOIqz-IZTdEYF1NomLpF0HUuI). It looks like `aiv2_...`
2. **A way to talk to Centaur** — pick one:
   - **Slack** (easiest): just @ the bot in `#ai-agent`
   - **Claude Code / Amp** (local): for building on your laptop before deploying

---

## What Can I Build?

You can build any of these — pick whatever excites you:

| What | Description | Example |
|------|-------------|---------|
| **Tool** | Connect Centaur to a new API or data source | A CoinGecko price checker, a Notion reader, a weather API |
| **Skill** | Teach Centaur a new multi-step workflow it can follow | "Archive Slack thread files to Google Drive" |
| **Workflow** | A durable, scheduled, or multi-step automation | A daily digest, a recurring monitor, a multi-agent pipeline |
| **Web App** | A frontend that talks to Centaur's API or other itnegrations | A dashboard, a chat UI, an internal tool |

---

## Option A: Build via Slack (Easiest)

You can build *everything* by talking to Centaur in Slack. Start a thread in `#ai-agent` and tell it what you want.

**Examples of things you can say:**

> "Create a new tool that wraps the Hacker News API. I want methods to get top stories, search stories, and get comments for a story."

> "Build me a workflow that runs every morning at 9am ET, checks the top 5 Hacker News stories, and posts a summary to `#daily-news`."

> "Deploy a Next.js web app from my repo `github.com/myname/my-app` and make it available at `my-app.svc-ai.dayno.xyz`."

Centaur will write the code, test it, and deploy it — all from the Slack thread.

---

## Option B: Build Locally (More Control)

If you prefer to code on your laptop (using Claude Code, Amp, Cursor, or just a text editor), you can build locally and test against the hosted Centaur API.

### Test your API key works

```bash
# Replace with your actual key
export CENTAUR_API_KEY="aiv2_your_key_here"

# Health check
curl -s https://svc-ai.dayno.xyz/health \
  -H "X-Api-Key: $CENTAUR_API_KEY"

# List available tools
curl -s https://svc-ai.dayno.xyz/tools \
  -H "X-Api-Key: $CENTAUR_API_KEY" | python3 -m json.tool
```

### Talk to a Centaur agent via the API

This is the full conversation loop — spawn an agent, send a message, run it, and stream the response:

```bash
export CENTAUR_API_KEY="aiv2_your_key_here"
THREAD_KEY="hackathon-$(whoami)-$(date +%s)"

# 1. Spawn an agent session
SPAWN=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/spawn \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"harness\":\"amp\"}")
ASSIGNMENT_GENERATION=$(echo "$SPAWN" | python3 -c "import sys,json; print(json.load(sys.stdin)['assignment_generation'])")

# 2. Send a message
curl -s -X POST https://svc-ai.dayno.xyz/agent/message \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${ASSIGNMENT_GENERATION},\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"text\":\"What tools do you have access to? List the top 10.\"}]}"

# 3. Execute (this kicks off the agent)
EXECUTE=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${ASSIGNMENT_GENERATION},\"harness\":\"amp\",\"delivery\":{\"platform\":\"dev\"}}")
EXECUTION_ID=$(echo "$EXECUTE" | python3 -c "import sys,json; print(json.load(sys.stdin)['execution_id'])")

# 4. Stream the response (Server-Sent Events)
curl -s -N "https://svc-ai.dayno.xyz/agent/threads/${THREAD_KEY}/events?execution_id=${EXECUTION_ID}&after_event_id=0" \
  -H "X-Api-Key: $CENTAUR_API_KEY"
```

### Call a tool directly

You can also call any Centaur tool directly via REST — no agent needed:

```bash
# Search the web
curl -s -X POST https://svc-ai.dayno.xyz/tools/websearch/search \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{"query": "latest ethereum news", "num_results": 3}' | python3 -m json.tool

# Discover what methods a tool has
curl -s https://svc-ai.dayno.xyz/tools/slack \
  -H "X-Api-Key: $CENTAUR_API_KEY" | python3 -m json.tool
```

---

## Building a Tool

A tool connects Centaur to an external API. Once deployed, any Centaur agent (including in Slack) can use it.

### Structure

```
tools/my-tool/
├── __init__.py        # Empty file
├── client.py          # Your API client (this is the important one)
├── pyproject.toml     # Package metadata
└── .env.example       # Document any required API keys
```

### Minimal example: a public API (no auth needed)

```python
# tools/hackernews/client.py
import httpx


class HackerNewsClient:
    """Hacker News API client."""

    def top_stories(self, limit: int = 10) -> list[dict]:
        """Get the current top stories from Hacker News."""
        with httpx.Client() as client:
            ids = client.get("https://hacker-news.firebaseio.com/v0/topstories.json").json()
            stories = []
            for story_id in ids[:limit]:
                story = client.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json").json()
                stories.append({"title": story.get("title"), "url": story.get("url"), "score": story.get("score")})
            return stories

    def get_item(self, item_id: int) -> dict:
        """Get a single item (story, comment, etc.) by ID."""
        with httpx.Client() as client:
            return client.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json").json()


def _client() -> HackerNewsClient:
    return HackerNewsClient()
```

```toml
# tools/hackernews/pyproject.toml
[project]
name = "hackernews"
description = "Hacker News API - top stories, items, and comments"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["httpx>=0.27.0"]

[tool.ai-v2]
module = "client.py"
```

### Minimal example: a tool that needs an API key

```python
# tools/my-api/client.py
import httpx
from centaur_sdk.tool_sdk import secret


class MyApiClient:
    def search(self, query: str, limit: int = 10) -> dict:
        """Search for things."""
        api_key = secret("MY_API_KEY")
        resp = httpx.get(
            "https://api.example.com/search",
            params={"q": query, "limit": limit},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        return resp.json()


def _client() -> MyApiClient:
    return MyApiClient()
```

### Adding your API key to 1Password

If your tool requires an API key for the external service, you **must** add it to 1Password so Centaur can access it in production.

1. Open 1Password → **Paradigm AI Secrets & API Keys** vault
2. Create a new item
3. **Title**: the exact env var name your code uses (e.g., `MY_API_KEY`)
4. Put the key value in the `password` or `credential` field
5. Save — Centaur refreshes secrets periodically

### Key rules

- **`client.py`** must have a `_client()` function at the bottom — this is how Centaur loads it
- **Public methods** become API endpoints automatically (e.g., `search()` → `POST /tools/my-tool/search`)
- **Methods starting with `_`** are private and won't be exposed
- **Use `secret("KEY_NAME")`** for API keys — never hardcode, never `os.getenv()`
- **API keys must be in 1Password** (see above) for the deployed instance to use them
- **Docstrings matter** — they become the tool description the agent sees

---

## Building a Skill

A skill teaches Centaur *how* to do something — a repeatable recipe it follows. Skills live in `.agents/skills/`.

### Structure

```
.agents/skills/my-skill/
├── SKILL.md           # Instructions the agent follows
└── scripts/           # Optional helper scripts
    └── do_thing.py
```

### Example SKILL.md

```markdown
---
name: my-cool-skill
description: "Does the cool thing. Use when asked to do the cool thing."
---

# My Cool Skill

## When To Use

Use this skill when the user asks to "do the cool thing" or "run cool analysis."

## Steps

1. First, gather the input from the user (what they want analyzed)
2. Call the websearch tool to find recent data
3. Summarize the findings in a table
4. Post the result back to the user

## Output Format

Always output a markdown table with columns: Name, Score, Link.
```

That's it — it's just a markdown file with instructions. Think of it as a recipe card.

---

## Building a Workflow

A workflow is a durable, multi-step automation that can sleep, retry, run agents, and survive crashes. Workflows live in `workflows/`.

### Simple example

```python
# workflows/morning_briefing.py
"""Workflow: morning briefing that runs an agent to summarize news."""

from dataclasses import dataclass
from typing import Any

from api.workflow_engine import WorkflowContext

WORKFLOW_NAME = "morning_briefing"


@dataclass
class Input:
    topic: str = "crypto"
    slack_channel: str = ""


async def handler(inp: Input, ctx: WorkflowContext) -> dict[str, Any]:
    # Step 1: ask the agent to research
    result = await ctx.run_agent(
        "research",
        text=f"Search for the latest news about {inp.topic} and summarize the top 5 stories.",
    )

    # Step 2: done — the result includes what the agent said
    return {"topic": inp.topic, "result": result}
```

### Starting a workflow via API

```bash
curl -s -X POST https://svc-ai.dayno.xyz/workflows/runs \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{
    "workflow_name": "morning_briefing",
    "input": {"topic": "ethereum", "slack_channel": "daily-news"}
  }' | python3 -m json.tool
```

---

## Building a Web App

You can deploy a web app (Next.js, Python, anything) that talks to Centaur's API. It runs on Centaur's infrastructure and gets a public URL.

### Using a template

The fastest path — fork one of these templates:

- **Next.js**: `paradigmxyz/centaur-template-nextjs`
- **Cloudflare Workers**: `paradigmxyz/centaur-template-cloudflare`

### Deploy via Slack

Tell Centaur in Slack:

> "Deploy a web app called `my-dashboard` from `github.com/myname/my-app`. It runs on port 3000."

Or via API:

```bash
curl -s -X POST https://svc-ai.dayno.xyz/apps \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{
    "name": "my-dashboard",
    "repo_url": "https://github.com/myname/my-app",
    "port": 3000
  }' | python3 -m json.tool
```

Your app will be live at `https://my-dashboard.svc-ai.dayno.xyz`.

---

## Deploying Your Work

Everything you build — tools, skills, workflows — goes live by landing on the `main` branch of `paradigmxyz/centaur`. Tools and workflows **hot-reload within seconds** of hitting `main` (no restart, no Docker rebuild).

**You do NOT need a GitHub account.** Every Centaur agent runs in a sandbox that has full git and `gh` CLI access. You just tell the agent what to deploy and it handles the branch, commit, PR, and merge for you. You can trigger this agent from anywhere — Slack, `curl`, your own app, whatever.

### Deploy via the API (works from anywhere)

Use the same `spawn → message → execute` flow to tell a Centaur agent to deploy your code. The agent runs in a sandbox with GitHub access and handles everything.

```bash
export CENTAUR_API_KEY="aiv2_your_key_here"
THREAD_KEY="deploy-$(date +%s)"

# 1. Spawn
SPAWN=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/spawn \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"harness\":\"amp\"}")
AG=$(echo "$SPAWN" | python3 -c "import sys,json; print(json.load(sys.stdin)['assignment_generation'])")

# 2. Send your deploy instructions (paste your code inline, or describe what you want)
curl -s -X POST https://svc-ai.dayno.xyz/agent/message \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"text\":\"Add a new tool called hackernews to tools/hackernews/ in paradigmxyz/centaur. Here is client.py:\\n\\nimport httpx\\n\\nclass HackerNewsClient:\\n    def top_stories(self, limit: int = 10) -> list[dict]:\\n        ...\\n\\ndef _client():\\n    return HackerNewsClient()\\n\\nCreate the pyproject.toml too. Then open a PR and merge it.\"}]}"

# 3. Execute — the agent does the rest (branch, commit, PR, merge)
EXECUTE=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"harness\":\"amp\",\"delivery\":{\"platform\":\"dev\"}}")
EXECUTION_ID=$(echo "$EXECUTE" | python3 -c "import sys,json; print(json.load(sys.stdin)['execution_id'])")

# 4. Stream the agent's progress
curl -s -N "https://svc-ai.dayno.xyz/agent/threads/${THREAD_KEY}/events?execution_id=${EXECUTION_ID}&after_event_id=0" \
  -H "X-Api-Key: $CENTAUR_API_KEY"
```

The agent will:
1. Run `git-branch paradigmxyz/centaur` to get a writable clone
2. Write your files to the correct directory
3. Commit, push, `gh pr create`, `gh pr merge`
4. Hot-reload kicks in — your tool/skill/workflow is live within seconds

This same flow works for **any modification** — adding a tool, fixing a bug in a tool, adding a skill, adding a workflow. Just describe what you want in the message.

### Deploy a web app

Web apps are deployed separately (they run as long-lived containers, not as code on `main`):

```bash
curl -s -X POST https://svc-ai.dayno.xyz/apps \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{
    "name": "my-dashboard",
    "repo_url": "https://github.com/myname/my-app",
    "port": 3000
  }'
```

Your app will be live at `https://my-dashboard.svc-ai.dayno.xyz`. You can also just tell an agent to do this — *"Deploy a web app called my-dashboard from github.com/myname/my-app on port 3000."*

### Run a workflow

Once a workflow is on `main`, trigger it via the API:

```bash
curl -s -X POST https://svc-ai.dayno.xyz/workflows/runs \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{"workflow_name": "morning_briefing", "input": {"topic": "ethereum"}}'
```

---

## Quick Reference

| I want to... | Do this |
|--------------|---------|
| Test my API key | `curl -s https://svc-ai.dayno.xyz/health -H "X-Api-Key: YOUR_KEY"` |
| See all available tools | `curl -s https://svc-ai.dayno.xyz/tools -H "X-Api-Key: YOUR_KEY"` |
| Call a tool directly | `curl -s -X POST https://svc-ai.dayno.xyz/tools/TOOL/METHOD -H "X-Api-Key: YOUR_KEY" -H "Content-Type: application/json" -d '{...}'` |
| Discover a tool's methods | `curl -s https://svc-ai.dayno.xyz/tools/TOOL -H "X-Api-Key: YOUR_KEY"` |
| Deploy a web app | Ask Centaur in Slack, or `POST /apps` |
| Start a workflow | `POST /workflows/runs` with workflow name and input |
| Check a workflow's status | `GET /workflows/runs/{run_id}` |

### Base URL

```
https://svc-ai.dayno.xyz
```

### Auth header (pick one)

```
X-Api-Key: aiv2_your_key
Authorization: Bearer aiv2_your_key
```

---

## FAQ

**Q: Should I build in Slack or locally?**
Either works! Slack is great for quick prototyping — just describe what you want and Centaur builds it. Local is better if you want more control or are iterating on something complex. You can start in Slack and move local (or vice versa) anytime.

**Q: Can I build a tool without an API key for the external service?**
Yes — many APIs are free/public (Hacker News, DeFi Llama, CoinDesk, Google News, Polymarket). For APIs that need keys, bring your own or ask in `#hackathon2026`.

**Q: Do I need a GitHub account?**
No. Use the `spawn → message → execute` API to tell a Centaur agent to deploy your code. The agent has full `gh` CLI access and handles branch, commit, PR, merge on your behalf. You just need your API key.

**Q: How do I make my tool available to everyone?**
It needs to land on `main` in `paradigmxyz/centaur`. Use the API to trigger an agent with your code and tell it to "add this to `tools/my-tool/`, open a PR, and merge it." Once on `main`, tools and workflows hot-reload in seconds.

**Q: Can I use Python libraries?**
Yes. Add them to your tool's `pyproject.toml` under `dependencies`. They get installed automatically.

**Q: What if I break something?**
You won't — your tool/skill/workflow runs in isolation. And we can always roll back. Ship it!

**Q: How do I see what Centaur already has?**
Ask Centaur! Or hit `GET /tools` to see all 60+ tools. For skills, check `.agents/skills/` in the repo.
