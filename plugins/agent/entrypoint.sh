#!/bin/bash
set -e

# Optional repo sync on start
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
