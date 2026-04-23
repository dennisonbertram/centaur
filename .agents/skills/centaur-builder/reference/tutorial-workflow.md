# Tutorial: Building a Workflow

End-to-end walkthrough: write a workflow locally, understand how it works, deploy it to Centaur, and trigger it.

We'll build a workflow that monitors a topic and posts a daily summary.

---

## What is a workflow?

A workflow is a durable Python automation. Unlike a one-shot agent turn, workflows can:

- **Sleep** and resume later (e.g., "run again tomorrow at 9am")
- **Run agents** as sub-steps (agent does the thinking, workflow handles orchestration)
- **Checkpoint** each step — if something crashes, it resumes where it left off
- **Loop** indefinitely (e.g., a recurring daily digest)

---

## Step 1: Write the workflow locally

Create a file anywhere on your machine:

```bash
mkdir -p my-hackathon-workflow
cd my-hackathon-workflow
```

**`topic_monitor.py`**:

```python
"""Workflow: monitors a topic and posts a daily summary to Slack."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

from api.workflow_engine import WorkflowContext

WORKFLOW_NAME = "topic_monitor"


@dataclass
class Input:
    topic: str = "crypto regulation"
    slack_channel: str = ""
    timezone: str = "America/New_York"
    run_hour: int = 9
    run_minute: int = 0
    max_iterations: int = 0  # 0 = run forever


async def handler(inp: Input, ctx: WorkflowContext) -> dict[str, Any]:
    """Run a daily monitoring loop."""

    iteration = 0

    while True:
        iteration += 1

        # Step 1: Ask an agent to research the topic
        result = await ctx.run_agent(
            f"research_{iteration}",
            text=(
                f"Search for the latest news and developments about '{inp.topic}' "
                f"from the past 24 hours. Summarize the top 5 most important items. "
                f"For each item, include: a one-line summary, the source, and why it matters. "
                f"Format as a numbered list."
            ),
        )

        # Step 2: Optionally post to Slack
        if inp.slack_channel and isinstance(result, dict):
            result_text = result.get("result_text", "")
            if result_text:
                await ctx.step(
                    f"post_slack_{iteration}",
                    lambda: {"posted": True},  # placeholder — agent already posted
                )

        # Step 3: Check if we should stop
        if inp.max_iterations > 0 and iteration >= inp.max_iterations:
            return {
                "status": "done",
                "iterations": iteration,
                "last_result": result,
            }

        # Step 4: Sleep until next run
        tz = ZoneInfo(inp.timezone)
        now = dt.datetime.now(dt.timezone.utc).astimezone(tz)
        next_run = now.replace(
            hour=inp.run_hour,
            minute=inp.run_minute,
            second=0,
            microsecond=0,
        )
        if next_run <= now:
            next_run += dt.timedelta(days=1)

        await ctx.sleep(f"wait_{iteration + 1}", next_run - now)
```

---

## Step 2: Understand the building blocks

Before testing, let's understand what each primitive does:

| Primitive | What it does | Example |
|-----------|-------------|---------|
| `ctx.run_agent(name, text=...)` | Runs a full Centaur agent turn and waits for the result | Research, summarize, analyze |
| `ctx.step(name, fn)` | Run a function exactly once; result is cached on replay | API calls, data transforms |
| `ctx.sleep(name, duration)` | Pause the workflow for a `timedelta` — the process actually stops and resumes later | Wait until tomorrow |
| `ctx.sleep_until(name, when)` | Pause until a specific datetime | Wait until Jan 1, 2027 |
| `ctx.wait_for_event(name, type, id)` | Pause until an external event arrives via `POST /workflows/events` | Wait for user approval |
| `ctx.run_workflow(name, wf_name, input)` | Start a child workflow and wait for it to finish | Orchestrate sub-tasks |
| `ctx.log(msg)` | Structured log (suppressed during replay) | Debug output |

---

## Step 3: Test locally (dry run)

Workflows need the Centaur workflow engine to actually run, so you can't fully execute them locally. But you can validate the code:

### Check syntax and imports

```bash
# Verify it parses correctly
python3 -c "
import ast
with open('topic_monitor.py') as f:
    tree = ast.parse(f.read())
print('✓ Syntax OK')

# Check the required exports exist
names = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
assert 'handler' in names, 'Missing handler function'
assert 'Input' in names, 'Missing Input dataclass'
print('✓ handler() found')
print('✓ Input dataclass found')
"

# Check WORKFLOW_NAME is set
python3 -c "
with open('topic_monitor.py') as f:
    content = f.read()
assert 'WORKFLOW_NAME' in content, 'Missing WORKFLOW_NAME'
print('✓ WORKFLOW_NAME found')
"
```

### Test the Input dataclass

```bash
python3 -c "
from dataclasses import dataclass, fields
import importlib.util, sys

spec = importlib.util.spec_from_file_location('topic_monitor', 'topic_monitor.py')
mod = importlib.util.module_from_spec(spec)

# We can't import api.workflow_engine locally, so mock it
sys.modules['api'] = type(sys)('api')
sys.modules['api.workflow_engine'] = type(sys)('api.workflow_engine')
sys.modules['api.workflow_engine'].WorkflowContext = object

spec.loader.exec_module(mod)

print(f'Workflow name: {mod.WORKFLOW_NAME}')
inp = mod.Input()
for f in fields(inp):
    print(f'  {f.name}: {getattr(inp, f.name)!r}')
"
```

This verifies your Input defaults and WORKFLOW_NAME are correct.

### Test with a one-shot agent first

Before deploying as a workflow, test the core logic as a plain agent turn:

```bash
export CENTAUR_API_KEY="aiv2_your_key_here"
THREAD_KEY="test-wf-logic-$(date +%s)"

SPAWN=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/spawn \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"harness\":\"amp\"}")
AG=$(echo "$SPAWN" | python3 -c "import sys,json; print(json.load(sys.stdin)['assignment_generation'])")

# Send the same prompt your workflow would send
curl -s -X POST https://svc-ai.dayno.xyz/agent/message \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"text\":\"Search for the latest news and developments about 'crypto regulation' from the past 24 hours. Summarize the top 5 most important items. For each item, include: a one-line summary, the source, and why it matters. Format as a numbered list.\"}]}"

EXECUTE=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"harness\":\"amp\",\"delivery\":{\"platform\":\"dev\"}}")
EXECUTION_ID=$(echo "$EXECUTE" | python3 -c "import sys,json; print(json.load(sys.stdin)['execution_id'])")

curl -s -N "https://svc-ai.dayno.xyz/agent/threads/${THREAD_KEY}/events?execution_id=${EXECUTION_ID}&after_event_id=0" \
  -H "X-Api-Key: $CENTAUR_API_KEY"
```

If the agent's output looks good, you know the workflow's core logic will work.

---

## Step 4: Deploy to Centaur

```bash
THREAD_KEY="deploy-wf-$(date +%s)"
WF_CODE=$(cat topic_monitor.py)

SPAWN=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/spawn \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"harness\":\"amp\"}")
AG=$(echo "$SPAWN" | python3 -c "import sys,json; print(json.load(sys.stdin)['assignment_generation'])")

MSG="Add a new workflow to paradigmxyz/centaur.

Create the file workflows/topic_monitor.py with this content:

\`\`\`python
${WF_CODE}
\`\`\`

Then open a PR and merge it."

curl -s -X POST https://svc-ai.dayno.xyz/agent/message \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"text\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$MSG")}]}"

EXECUTE=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"harness\":\"amp\",\"delivery\":{\"platform\":\"dev\"}}")
EXECUTION_ID=$(echo "$EXECUTE" | python3 -c "import sys,json; print(json.load(sys.stdin)['execution_id'])")

curl -s -N "https://svc-ai.dayno.xyz/agent/threads/${THREAD_KEY}/events?execution_id=${EXECUTION_ID}&after_event_id=0" \
  -H "X-Api-Key: $CENTAUR_API_KEY"
```

---

## Step 5: Trigger the workflow

After the PR merges and hot-reload picks it up:

```bash
# Start a single run (max_iterations=1 for testing)
curl -s -X POST https://svc-ai.dayno.xyz/workflows/runs \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{
    "workflow_name": "topic_monitor",
    "input": {
      "topic": "crypto regulation",
      "max_iterations": 1
    }
  }' | python3 -m json.tool
```

Save the `run_id` from the response.

### Check status

```bash
curl -s https://svc-ai.dayno.xyz/workflows/runs/<run_id> \
  -H "X-Api-Key: $CENTAUR_API_KEY" | python3 -m json.tool
```

### Start the recurring version

Once the single run works, start the real recurring one:

```bash
curl -s -X POST https://svc-ai.dayno.xyz/workflows/runs \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d '{
    "workflow_name": "topic_monitor",
    "input": {
      "topic": "crypto regulation",
      "slack_channel": "#daily-news",
      "run_hour": 9,
      "max_iterations": 0
    }
  }' | python3 -m json.tool
```

### Cancel a running workflow

```bash
curl -s -X POST https://svc-ai.dayno.xyz/workflows/runs/<run_id>/cancel \
  -H "X-Api-Key: $CENTAUR_API_KEY"
```

---

## Common patterns

### One-shot workflow (no loop)

```python
async def handler(inp: Input, ctx: WorkflowContext) -> dict[str, Any]:
    data = await ctx.step("fetch", lambda: fetch_some_data())
    result = await ctx.run_agent("analyze", text=f"Analyze: {data}")
    return {"result": result}
```

### Workflow with human approval

```python
async def handler(inp: Input, ctx: WorkflowContext) -> dict[str, Any]:
    draft = await ctx.run_agent("draft", text="Draft a report...")

    # Post draft and wait for someone to approve via POST /workflows/events
    approval = await ctx.wait_for_event(
        "wait_approval",
        event_type="approval",
        correlation_id=f"report-{ctx.run_id}",
    )

    final = await ctx.run_agent("finalize", text=f"Finalize with feedback: {approval}")
    return {"final": final}
```

### Multi-agent workflow

```python
async def handler(inp: Input, ctx: WorkflowContext) -> dict[str, Any]:
    research = await ctx.run_agent("research", text="Research topic X")
    analysis = await ctx.run_agent("analyze", text=f"Analyze: {research}")
    summary = await ctx.run_agent("summarize", text=f"Summarize for executives: {analysis}")
    return {"summary": summary}
```

---

## Checklist

- [ ] File has `WORKFLOW_NAME = "..."` at module level
- [ ] File has `async def handler(inp, ctx)` function
- [ ] File has `Input` dataclass with sensible defaults
- [ ] Imports use `from api.workflow_engine import WorkflowContext`
- [ ] Tested the core agent prompt as a standalone agent turn
- [ ] Validated syntax and required exports locally
- [ ] Deployed via agent, triggered with `POST /workflows/runs`
- [ ] Verified completion with `GET /workflows/runs/<id>`
