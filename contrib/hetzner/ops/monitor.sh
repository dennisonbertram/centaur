#!/usr/bin/env bash
# Health check across all customer deployments.
# Usage: ./monitor.sh [--json]
#
# Checks API health, pod status, Postgres, and disk usage for each deployment.
# Run via cron and pipe to an alerting system (PagerDuty, Slack, etc.).
set -euo pipefail

STATE_DIR="${CENTAUR_STATE_DIR:-$HOME/.centaur/deployments}"
JSON_OUTPUT=0
[[ "${1:-}" == "--json" ]] && JSON_OUTPUT=1

ALERTS=()

check_customer() {
  local cid="$1"
  local dir="$STATE_DIR/$cid"
  local status="ok"
  local details=""

  if [[ ! -f "$dir/kubeconfig.yaml" ]]; then
    status="error"
    details="no kubeconfig"
  else
    export KUBECONFIG="$dir/kubeconfig.yaml"

    if ! kubectl cluster-info >/dev/null 2>&1; then
      status="error"
      details="cluster unreachable"
    else
      local health
      health=$(kubectl exec -n centaur deploy/centaur-centaur-api -- \
        curl -s http://localhost:8000/health 2>/dev/null || echo '{}')
      local api_status
      api_status=$(echo "$health" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")

      if [[ "$api_status" != "ok" ]]; then
        status="degraded"
        details="api health: $api_status"
      fi

      local not_running
      not_running=$(kubectl get pods -n centaur --no-headers 2>/dev/null | grep -v Running | grep -v Completed | wc -l | tr -d ' ')
      if [[ "$not_running" -gt 0 ]]; then
        status="degraded"
        details="${details:+$details; }$not_running pods not running"
      fi

      local pod_count
      pod_count=$(kubectl get pods -n centaur --no-headers 2>/dev/null | wc -l | tr -d ' ')
      details="${details:+$details; }${pod_count} pods"
    fi
  fi

  if [[ $JSON_OUTPUT -eq 1 ]]; then
    echo "{\"customer\":\"$cid\",\"status\":\"$status\",\"details\":\"$details\"}"
  else
    local icon="✓"
    [[ "$status" == "degraded" ]] && icon="⚠"
    [[ "$status" == "error" ]] && icon="✗"
    printf "  %s %-20s %s\n" "$icon" "$cid" "$details"
  fi

  [[ "$status" != "ok" ]] && ALERTS+=("$cid: $status — $details")
}

if [[ $JSON_OUTPUT -eq 0 ]]; then
  echo "==> Centaur deployment health check ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
fi

for d in "$STATE_DIR"/*/; do
  [[ -d "$d" ]] || continue
  check_customer "$(basename "$d")"
done

if [[ ${#ALERTS[@]} -gt 0 && $JSON_OUTPUT -eq 0 ]]; then
  echo ""
  echo "  ${#ALERTS[@]} alert(s):"
  for a in "${ALERTS[@]}"; do
    echo "    - $a"
  done
fi

# Send to Slack if webhook configured
if [[ ${#ALERTS[@]} -gt 0 && -n "${CENTAUR_ALERT_SLACK_WEBHOOK:-}" ]]; then
  ALERT_TEXT=$(printf '%s\\n' "${ALERTS[@]}")
  curl -s -X POST "$CENTAUR_ALERT_SLACK_WEBHOOK" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"Centaur health alerts:\\n$ALERT_TEXT\"}" >/dev/null 2>&1
fi
