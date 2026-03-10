#!/usr/bin/env bash
set -euo pipefail

source /app/bootstrap-secrets.sh

bootstrap_required_secrets WEB_API_KEY DATABASE_URL

exec "$@"
