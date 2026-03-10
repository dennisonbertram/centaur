#!/usr/bin/env bash
set -euo pipefail

source /app/bootstrap-secrets.sh

bootstrap_required_secrets AUTH_COOKIE_KEY UI_PASSWORD

exec "$@"
