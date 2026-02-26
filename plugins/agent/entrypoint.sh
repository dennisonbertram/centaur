#!/bin/bash
set -e

HOME_DIR="$(eval echo ~)"
MCP_URL="${AI_V2_API_URL:-http://localhost:8000}/mcp/"
MCP_KEY="${AI_V2_API_KEY:-}"

# Write MCP configs for all harnesses
if [ -n "$MCP_KEY" ]; then
    # Amp
    mkdir -p "$HOME_DIR/.config/amp"
    cat > "$HOME_DIR/.config/amp/settings.json" <<EOF
{"amp.mcpServers":{"tempo-ai":{"url":"${MCP_URL}","headers":{"Authorization":"Bearer ${MCP_KEY}"}}}}
EOF

    # Claude Code
    cat > "$HOME_DIR/.claude.json" <<EOF
{"mcpServers":{"tempo-ai":{"type":"http","url":"${MCP_URL}","headers":{"Authorization":"Bearer ${MCP_KEY}"}}}}
EOF

    # Codex — use `codex mcp add` if available, else write config directly
    mkdir -p "$HOME_DIR/.codex"
    if command -v codex >/dev/null 2>&1; then
        codex mcp add tempo-ai --url "${MCP_URL}" 2>/dev/null || true
    fi
    cat > "$HOME_DIR/.codex/config.toml" <<EOF
[mcp_servers.tempo-ai]
url = "${MCP_URL}"
EOF
fi

# Codex auth — login with API key if available
CODEX_KEY="${CODEX_API_KEY:-${OPENAI_API_KEY:-}}"
if [ -n "$CODEX_KEY" ]; then
    if command -v codex >/dev/null 2>&1; then
        echo "$CODEX_KEY" | codex login --with-api-key 2>/dev/null || true
    fi
fi

# Optional repo sync
if [ "${SYNC_ON_START:-false}" = "true" ]; then
    for dir in /repos/tempoxyz/*/; do
        if [ -d "$dir/.git" ]; then
            echo "Updating $(basename "$dir")..."
            cd "$dir" && git fetch origin && git reset --hard origin/HEAD 2>/dev/null || true
            cd /repos
        fi
    done
fi

exec "$@"
