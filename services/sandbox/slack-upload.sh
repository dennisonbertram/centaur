#!/bin/bash
# slack-upload — upload a file to the current Slack thread
# Usage: slack-upload <file_path> [comment]
set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: slack-upload <file_path> [comment]" >&2
  exit 1
fi

FILE="$1"
COMMENT="${2:-}"

if [ ! -f "$FILE" ]; then
  echo "Error: file not found: $FILE" >&2
  exit 1
fi

FILE="$(realpath "$FILE")"
CHANNEL="${SLACK_CHANNEL:?SLACK_CHANNEL not set}"
THREAD="${SLACK_THREAD_TS:?SLACK_THREAD_TS not set}"
FILENAME="$(basename "$FILE")"

extract_link() {
  printf '%s' "$1" | jq -r '.permalink // .file.permalink // empty' 2>/dev/null || true
}

run_upload() {
  local body="$1"

  set +e
  RESP="$(call slack upload_file "$body" 2>&1)"
  STATUS=$?
  set -e

  LINK="$(extract_link "$RESP")"
}

PRIMARY_BODY=$(jq -nc \
  --arg channel "$CHANNEL" \
  --arg file_path "$FILE" \
  --arg title "$FILENAME" \
  --arg comment "$COMMENT" \
  --arg thread_ts "$THREAD" \
  '{channel: $channel, file_path: $file_path, title: $title, comment: $comment, thread_ts: $thread_ts}')

run_upload "$PRIMARY_BODY"
if [ -n "$LINK" ]; then
  echo "$LINK"
  exit 0
fi

PRIMARY_RESP="$RESP"
PRIMARY_STATUS="$STATUS"

# Fall back to inline content if the direct file upload path fails.
B64="$(base64 -w0 "$FILE")"
FALLBACK_BODY=$(jq -nc \
  --arg channel "$CHANNEL" \
  --arg content_base64 "$B64" \
  --arg filename "$FILENAME" \
  --arg title "$FILENAME" \
  --arg comment "$COMMENT" \
  --arg thread_ts "$THREAD" \
  '{channel: $channel, content_base64: $content_base64, filename: $filename, title: $title, comment: $comment, thread_ts: $thread_ts}')

run_upload "$FALLBACK_BODY"
if [ -n "$LINK" ]; then
  echo "$LINK"
  exit 0
fi

echo "Error: upload failed" >&2
jq -nc \
  --arg file_path "$FILE" \
  --argjson primary_status "$PRIMARY_STATUS" \
  --arg primary_response "$PRIMARY_RESP" \
  --argjson fallback_status "$STATUS" \
  --arg fallback_response "$RESP" \
  '{error: "upload_failed", file_path: $file_path, primary_status: $primary_status, primary_response: $primary_response, fallback_status: $fallback_status, fallback_response: $fallback_response}' >&2
exit 1
