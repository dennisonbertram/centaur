#!/usr/bin/env bash
# centaur-run — one-shot helper: spawn an agent, send a message, execute, and stream the result.
#
# Usage:
#   centaur-run "Your prompt here"
#
# Requires:
#   CENTAUR_API_KEY  — your hackathon API key (aiv2_...)
#
# Examples:
#   centaur-run "What tools do you have access to?"
#   centaur-run "Add a new tool called hackernews to tools/hackernews/ in paradigmxyz/centaur. <paste code>. Open a PR and merge it."

set -euo pipefail

API="${CENTAUR_API_URL:-https://svc-ai.dayno.xyz}"
KEY="${CENTAUR_API_KEY:?Set CENTAUR_API_KEY to your hackathon API key}"
PROMPT="${1:?Usage: centaur-run \"your prompt here\"}"
THREAD_KEY="hackathon-$(date +%s)-$$"

json_val() { python3 -c "import sys,json; print(json.load(sys.stdin)['$1'])"; }

# 1. Spawn
SPAWN=$(curl -sf -X POST "$API/agent/spawn" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"harness\":\"amp\"}")
AG=$(echo "$SPAWN" | json_val assignment_generation)

# 2. Message
curl -sf -X POST "$API/agent/message" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"text\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$PROMPT")}]}" >/dev/null

# 3. Execute
EXECUTE=$(curl -sf -X POST "$API/agent/execute" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"harness\":\"amp\",\"delivery\":{\"platform\":\"dev\"}}")
EXECUTION_ID=$(echo "$EXECUTE" | json_val execution_id)

echo "Thread: ${THREAD_KEY}"
echo "Execution: ${EXECUTION_ID}"
echo "Streaming events..."
echo "---"

# 4. Stream
curl -sN "$API/agent/threads/${THREAD_KEY}/events?execution_id=${EXECUTION_ID}&after_event_id=0" \
  -H "X-Api-Key: $KEY"
