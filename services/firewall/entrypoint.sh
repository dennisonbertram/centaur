#!/usr/bin/env bash
set -euo pipefail

CONFDIR="/home/mitmproxy/.mitmproxy"
CERT_SHARE="/certs"
SECRET_MANAGER_URL="${SECRET_MANAGER_URL:-http://secrets:8100}"

mkdir -p "$CONFDIR" "$CERT_SHARE"

# ── Load persistent CA if available (fast, non-blocking) ──────────────────
CA_CERT=$(curl -sf --max-time 2 "${SECRET_MANAGER_URL}/secrets/FIREWALL_CA_CERT" | jq -r '.value // empty' 2>/dev/null || true)
CA_KEY=$(curl -sf --max-time 2 "${SECRET_MANAGER_URL}/secrets/FIREWALL_CA_KEY" | jq -r '.value // empty' 2>/dev/null || true)

if [ -n "$CA_CERT" ] && [ -n "$CA_KEY" ]; then
    printf '%s\n%s\n' "$CA_KEY" "$CA_CERT" > "$CONFDIR/mitmproxy-ca.pem"
    echo "[firewall] loaded CA from secrets service"
else
    echo "[firewall] no CA in secrets — mitmproxy will auto-generate"
fi
unset CA_CERT CA_KEY

# ── Share CA cert with sandboxes (background) ─────────────────────────────
(
    for _ in $(seq 1 30); do
        [ -f "$CONFDIR/mitmproxy-ca-cert.pem" ] && break
        sleep 0.5
    done
    if [ -f "$CONFDIR/mitmproxy-ca-cert.pem" ]; then
        cp "$CONFDIR/mitmproxy-ca-cert.pem" "$CERT_SHARE/ca-cert.pem"
        echo "[firewall] CA cert shared at /certs/ca-cert.pem"
    fi
) &

# ── Start mitmdump ────────────────────────────────────────────────────────
exec mitmdump \
    --listen-port 8080 \
    --set confdir="$CONFDIR" \
    --set connection_strategy=lazy \
    -s /app/addon.py \
    "$@"
