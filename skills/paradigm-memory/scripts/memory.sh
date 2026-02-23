#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$SKILL_DIR/.env"

BASE="${PARADIGM_MEMORY_URL}"
AUTH="Authorization: Bearer ${PARADIGM_MEMORY_KEY}"

cmd="${1:-help}"
shift || true

curl_get() { curl -s -H "$AUTH" "$@"; }
curl_post() { curl -s -H "$AUTH" -H "Content-Type: application/json" "$@"; }

case "$cmd" in
  search)
    query="$1"; shift || true
    sources=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --sources) sources="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    body="{\"query\":\"$query\"}"
    if [[ -n "$sources" ]]; then
      IFS=',' read -ra src_arr <<< "$sources"
      src_json=$(printf '"%s",' "${src_arr[@]}")
      body="{\"query\":\"$query\",\"sources\":[${src_json%,}]}"
    fi
    curl_post -X POST "$BASE/api/search" -d "$body"
    ;;

  sql)
    query="$1"
    curl_post -X POST "$BASE/api/search/sql" -d "{\"query\":\"$query\"}"
    ;;

  timeline)
    days=7; source_filter=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --days) days="$2"; shift 2 ;;
        --source) source_filter="&source=$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    curl_get "$BASE/api/query/timeline?days=$days$source_filter"
    ;;

  people)
    curl_get "$BASE/api/query/people"
    ;;

  person)
    curl_get "$BASE/api/query/people/$1"
    ;;

  slack-messages)
    params=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --channel) params="${params}&channel=$2"; shift 2 ;;
        --user) params="${params}&user=$2"; shift 2 ;;
        --text) params="${params}&text=$2"; shift 2 ;;
        --limit) params="${params}&limit=$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    curl_get "$BASE/api/query/slack/messages?${params#&}"
    ;;

  slack-threads)
    params=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --channel) params="${params}&channel=$2"; shift 2 ;;
        --limit) params="${params}&limit=$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    curl_get "$BASE/api/query/slack/threads?${params#&}"
    ;;

  github-prs)
    params=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --repo) params="${params}&repo=$2"; shift 2 ;;
        --author) params="${params}&author=$2"; shift 2 ;;
        --state) params="${params}&state=$2"; shift 2 ;;
        --limit) params="${params}&limit=$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    curl_get "$BASE/api/query/github/prs?${params#&}"
    ;;

  linear-issues)
    params=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --state) params="${params}&state=$2"; shift 2 ;;
        --assignee) params="${params}&assignee=$2"; shift 2 ;;
        --limit) params="${params}&limit=$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    curl_get "$BASE/api/query/linear/issues?${params#&}"
    ;;

  sources)
    curl_get "$BASE/api/search/sources"
    ;;

  sync-status)
    curl_get "$BASE/api/sync/status"
    ;;

  sync-runs)
    curl_get "$BASE/api/sync/runs"
    ;;

  health)
    curl_get "$BASE/health"
    ;;

  help|*)
    cat <<EOF
Usage: memory.sh <command> [options]

Commands:
  search <query> [--sources s1,s2]     Hybrid search
  sql <query>                          Read-only SQL
  timeline [--days N] [--source S]     Activity timeline
  people                               List people
  person <slug>                        Get person
  slack-messages [--channel C] [--text T] [--user U]
  slack-threads [--channel C]
  github-prs [--repo R] [--author A] [--state S]
  linear-issues [--state S] [--assignee A]
  sources                              List sources
  sync-status                          Sync cursor state
  sync-runs                            Recent sync runs
  health                               API health
EOF
    ;;
esac
