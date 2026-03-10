#!/usr/bin/env bash
set -euo pipefail

source /app/bootstrap-secrets.sh

# PGBouncer uses PGBOUNCER_DATABASE_URL from secrets, mapped to DATABASE_URL
# which the edoburu/pgbouncer image reads to auto-generate pgbouncer.ini
bootstrap_required_secrets PGBOUNCER_DATABASE_URL

export DATABASE_URL="$PGBOUNCER_DATABASE_URL"

# Hand off to the upstream edoburu/pgbouncer entrypoint
exec /entrypoint.sh "$@"
