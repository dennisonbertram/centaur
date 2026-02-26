#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# 1Password bootstrap — sign in, load secrets as env vars, sign out.
#
# Required env vars:
#   OP_EMAIL          — e.g. svc_ai@paradigm.xyz
#   OP_SECRET_KEY     — account secret key
#   OP_MASTER_PASSWORD — account master password
#   OP_ACCOUNT        — e.g. paradigm.1password.com  (default)
#   OP_VAULT          — vault to read from             (default: AI-V2)
#
# If any are missing, skip 1Password and rely on .env / env vars.
# ---------------------------------------------------------------------------

OP_ACCOUNT="${OP_ACCOUNT:-paradigm.1password.com}"
OP_VAULT="${OP_VAULT:-AI-V2}"

if [[ -n "${OP_EMAIL:-}" && -n "${OP_SECRET_KEY:-}" && -n "${OP_MASTER_PASSWORD:-}" ]]; then
    echo "[entrypoint] signing in to 1Password as ${OP_EMAIL}..."

    # Sign in (non-interactive) — returns a session token
    SESSION_TOKEN=$(echo "${OP_MASTER_PASSWORD}" | op signin \
        --account "${OP_ACCOUNT}" \
        --raw 2>/dev/null) || {

        # Account might not be added yet — add + signin in one step
        SESSION_TOKEN=$(echo "${OP_MASTER_PASSWORD}" | op account add \
            --address "${OP_ACCOUNT}" \
            --email "${OP_EMAIL}" \
            --secret-key "${OP_SECRET_KEY}" \
            --signin --raw 2>/dev/null) || true
    }

    if [[ -n "${SESSION_TOKEN:-}" ]]; then
        export OP_SESSION_TOKEN="${SESSION_TOKEN}"

        echo "[entrypoint] loading secrets from vault '${OP_VAULT}'..."

        # List all items in the vault, read each password field, export as env var.
        # Item titles become env var names (uppercase, spaces/dashes → underscores).
        while IFS=$'\t' read -r item_id item_title; do
            # Normalise title → ENV_VAR_NAME
            env_name=$(echo "${item_title}" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9]/_/g')

            # Skip if already set in environment (explicit env takes precedence)
            if [[ -n "${!env_name:-}" ]]; then
                continue
            fi

            value=$(op read "op://${OP_VAULT}/${item_id}/password" --no-newline 2>/dev/null) || continue
            if [[ -n "${value}" ]]; then
                export "${env_name}=${value}"
            fi
        done < <(op item list --vault "${OP_VAULT}" --format json 2>/dev/null \
            | python3 -c "import sys,json; [print(f'{i[\"id\"]}\t{i[\"title\"]}') for i in json.load(sys.stdin)]" 2>/dev/null)

        echo "[entrypoint] signing out of 1Password..."
        op signout --account "${OP_ACCOUNT}" --forget 2>/dev/null || true
        unset OP_SESSION_TOKEN
    else
        echo "[entrypoint] 1Password signin failed — falling back to env vars"
    fi
else
    echo "[entrypoint] 1Password credentials not set — using env vars only"
fi

# Clear sensitive bootstrap vars so they don't leak to the app
unset OP_MASTER_PASSWORD OP_SECRET_KEY

exec "$@"
