#!/usr/bin/env bash
#
# Slackbot integration tests — sends signed Slack webhook payloads to the
# running slackbot service and verifies responses.
#
# Usage:
#   ./integration-slackbot.sh                          # defaults: slackbot at localhost:3001
#   SLACKBOT_URL=http://slackbot:3001 ./integration-slackbot.sh  # inside docker network
#
# Requires:  SLACK_SIGNING_SECRET in env (or sourced from .env).
#            The slackbot service must be running.

set -euo pipefail

SLACKBOT_URL="${SLACKBOT_URL:-http://localhost:3001}"
ENDPOINT="${SLACKBOT_URL}/api/slack/events"

# ── Load .env if SLACK_SIGNING_SECRET not already set ────────────────────────
if [[ -z "${SLACK_SIGNING_SECRET:-}" ]]; then
  ENV_FILE="${ENV_FILE:-.env}"
  if [[ -f "$ENV_FILE" ]]; then
    SLACK_SIGNING_SECRET=$(grep -E '^SLACK_SIGNING_SECRET=' "$ENV_FILE" | head -1 | cut -d= -f2-)
  fi
fi

if [[ -z "${SLACK_SIGNING_SECRET:-}" ]]; then
  echo "FATAL: SLACK_SIGNING_SECRET not set. Export it or add to .env."
  exit 1
fi

# ── Helpers ──────────────────────────────────────────────────────────────────

passed=0
failed=0
total=0

sign_and_send() {
  local body="$1"
  local desc="$2"
  local expect_status="${3:-200}"

  total=$((total + 1))
  local ts
  ts=$(date +%s)
  local sig_base="v0:${ts}:${body}"
  local hmac
  hmac=$(printf '%s' "$sig_base" | openssl dgst -sha256 -hmac "$SLACK_SIGNING_SECRET" | awk '{print $NF}')
  local signature="v0=${hmac}"

  local http_code
  local response
  response=$(curl -s -o /dev/stderr -w "%{http_code}" \
    -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "x-slack-signature: $signature" \
    -H "x-slack-request-timestamp: $ts" \
    -d "$body" 2>&1)
  http_code="${response: -3}"
  local resp_body="${response%???}"

  if [[ "$http_code" == "$expect_status" ]]; then
    passed=$((passed + 1))
    echo "  ✓ ${desc}  (${http_code})"
  else
    failed=$((failed + 1))
    echo "  ✗ ${desc}  (expected ${expect_status}, got ${http_code})"
    echo "    body: ${resp_body:0:200}"
  fi
}

send_bad_sig() {
  local body="$1"
  local desc="$2"
  local expect_status="${3:-401}"

  total=$((total + 1))
  local ts
  ts=$(date +%s)

  local http_code
  local response
  response=$(curl -s -o /dev/stderr -w "%{http_code}" \
    -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "x-slack-signature: v0=deadbeef" \
    -H "x-slack-request-timestamp: $ts" \
    -d "$body" 2>&1)
  http_code="${response: -3}"
  local resp_body="${response%???}"

  if [[ "$http_code" == "$expect_status" ]]; then
    passed=$((passed + 1))
    echo "  ✓ ${desc}  (${http_code})"
  else
    failed=$((failed + 1))
    echo "  ✗ ${desc}  (expected ${expect_status}, got ${http_code})"
    echo "    body: ${resp_body:0:200}"
  fi
}

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Slackbot Integration Tests"
echo "  endpoint: ${ENDPOINT}"
echo "═══════════════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────────────────────
# 1. URL verification challenge
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "── URL Verification ──"

sign_and_send \
  '{"type":"url_verification","challenge":"test-challenge-integration"}' \
  "url_verification returns challenge"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Signature rejection
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "── Signature Rejection ──"

send_bad_sig \
  '{"type":"url_verification","challenge":"should-fail"}' \
  "bad signature → 401"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Event callback — app_mention with no files (smoke test)
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "── Event Callbacks ──"

# Slack expects a 200 acknowledgement quickly; the bot processes async.
# We just verify the webhook returns 200 (not 500/503).

MENTION_BODY=$(cat <<'EOF'
{
  "type": "event_callback",
  "team_id": "T_TEST",
  "event": {
    "type": "app_mention",
    "user": "U_TESTER",
    "text": "<@U_BOT> integration test ping",
    "ts": "1700000001.000001",
    "channel": "C_TESTCHAN",
    "thread_ts": "1700000001.000001"
  }
}
EOF
)
sign_and_send "$MENTION_BODY" "app_mention (no files) → 200"

# ─────────────────────────────────────────────────────────────────────────────
# 4. Event callback — app_mention WITH image attachment
# ─────────────────────────────────────────────────────────────────────────────

MENTION_WITH_IMAGE=$(cat <<'EOF'
{
  "type": "event_callback",
  "team_id": "T_TEST",
  "event": {
    "type": "app_mention",
    "user": "U_TESTER",
    "text": "<@U_BOT> what is in this image?",
    "ts": "1700000002.000001",
    "channel": "C_TESTCHAN",
    "thread_ts": "1700000002.000001",
    "files": [
      {
        "id": "F_TEST_IMG",
        "name": "screenshot.png",
        "mimetype": "image/png",
        "url_private": "https://files.slack.com/test/screenshot.png",
        "size": 45000,
        "original_w": 1920,
        "original_h": 1080
      }
    ]
  }
}
EOF
)
sign_and_send "$MENTION_WITH_IMAGE" "app_mention with image attachment → 200"

# ─────────────────────────────────────────────────────────────────────────────
# 5. Event callback — app_mention with PDF attachment
# ─────────────────────────────────────────────────────────────────────────────

MENTION_WITH_PDF=$(cat <<'EOF'
{
  "type": "event_callback",
  "team_id": "T_TEST",
  "event": {
    "type": "app_mention",
    "user": "U_TESTER",
    "text": "<@U_BOT> summarize this doc",
    "ts": "1700000003.000001",
    "channel": "C_TESTCHAN",
    "thread_ts": "1700000003.000001",
    "files": [
      {
        "id": "F_TEST_PDF",
        "name": "report.pdf",
        "mimetype": "application/pdf",
        "url_private": "https://files.slack.com/test/report.pdf",
        "size": 120000
      }
    ]
  }
}
EOF
)
sign_and_send "$MENTION_WITH_PDF" "app_mention with PDF attachment → 200"

# ─────────────────────────────────────────────────────────────────────────────
# 6. Event callback — app_mention with mixed attachments
# ─────────────────────────────────────────────────────────────────────────────

MENTION_WITH_MIXED=$(cat <<'EOF'
{
  "type": "event_callback",
  "team_id": "T_TEST",
  "event": {
    "type": "app_mention",
    "user": "U_TESTER",
    "text": "<@U_BOT> analyze these files",
    "ts": "1700000004.000001",
    "channel": "C_TESTCHAN",
    "thread_ts": "1700000004.000001",
    "files": [
      {
        "id": "F_TEST_IMG2",
        "name": "chart.jpg",
        "mimetype": "image/jpeg",
        "url_private": "https://files.slack.com/test/chart.jpg",
        "size": 80000,
        "original_w": 800,
        "original_h": 600
      },
      {
        "id": "F_TEST_CSV",
        "name": "data.csv",
        "mimetype": "text/csv",
        "url_private": "https://files.slack.com/test/data.csv",
        "size": 5000
      }
    ]
  }
}
EOF
)
sign_and_send "$MENTION_WITH_MIXED" "app_mention with mixed attachments → 200"

# ─────────────────────────────────────────────────────────────────────────────
# 7. Event callback — message in subscribed thread (no mention)
# ─────────────────────────────────────────────────────────────────────────────

THREAD_MESSAGE=$(cat <<'EOF'
{
  "type": "event_callback",
  "team_id": "T_TEST",
  "event": {
    "type": "message",
    "user": "U_TESTER",
    "text": "here is more context",
    "ts": "1700000005.000001",
    "channel": "C_TESTCHAN",
    "thread_ts": "1700000001.000001"
  }
}
EOF
)
sign_and_send "$THREAD_MESSAGE" "thread message (no mention) → 200"

# ─────────────────────────────────────────────────────────────────────────────
# 8. Event callback — message with file in subscribed thread
# ─────────────────────────────────────────────────────────────────────────────

THREAD_MESSAGE_FILE=$(cat <<'EOF'
{
  "type": "event_callback",
  "team_id": "T_TEST",
  "event": {
    "type": "message",
    "user": "U_TESTER",
    "text": "",
    "ts": "1700000006.000001",
    "channel": "C_TESTCHAN",
    "thread_ts": "1700000001.000001",
    "files": [
      {
        "id": "F_THREAD_IMG",
        "name": "followup.png",
        "mimetype": "image/png",
        "url_private": "https://files.slack.com/test/followup.png",
        "size": 30000
      }
    ]
  }
}
EOF
)
sign_and_send "$THREAD_MESSAGE_FILE" "thread message with file attachment → 200"

# ─────────────────────────────────────────────────────────────────────────────
# 9. Invalid JSON body
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "── Edge Cases ──"

sign_and_send "not-json" "invalid JSON body → 400" "400"

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Results: ${passed} passed, ${failed} failed (${total} total)"
echo "═══════════════════════════════════════════════════"
echo ""

if [[ $failed -gt 0 ]]; then
  exit 1
fi
