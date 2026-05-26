#!/usr/bin/env bash
# Backup Postgres for a customer deployment.
# Usage: ./backup.sh <customer-id>
#
# Dumps the Centaur Postgres database and stores it in Hetzner Object Storage
# or a local directory. Run via cron for scheduled backups.
set -euo pipefail

CUSTOMER_ID="${1:?Usage: backup.sh <customer-id>}"
STATE_DIR="${CENTAUR_STATE_DIR:-$HOME/.centaur/deployments}"
BACKUP_DIR="${CENTAUR_BACKUP_DIR:-$HOME/.centaur/backups}"
DIR="$STATE_DIR/$CUSTOMER_ID"

if [[ ! -f "$DIR/kubeconfig.yaml" ]]; then
  echo "FATAL: No kubeconfig for $CUSTOMER_ID" >&2
  exit 1
fi

export KUBECONFIG="$DIR/kubeconfig.yaml"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/$CUSTOMER_ID/centaur-$TIMESTAMP.sql.gz"
mkdir -p "$(dirname "$BACKUP_FILE")"

echo "Backing up $CUSTOMER_ID to $BACKUP_FILE..."

kubectl exec -n centaur statefulset/centaur-centaur-postgres -- \
  pg_dump -U tempo -d ai_v2 --no-owner --no-privileges 2>/dev/null \
  | gzip > "$BACKUP_FILE"

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Done: $BACKUP_FILE ($SIZE)"

# Prune old backups (keep last 30)
KEPT=0
for f in $(ls -t "$BACKUP_DIR/$CUSTOMER_ID"/centaur-*.sql.gz 2>/dev/null); do
  KEPT=$((KEPT + 1))
  if [[ $KEPT -gt 30 ]]; then
    rm -f "$f"
    echo "Pruned: $(basename "$f")"
  fi
done

# Upload to Hetzner Object Storage if configured
if [[ -n "${CENTAUR_S3_BUCKET:-}" ]]; then
  S3_KEY="backups/$CUSTOMER_ID/centaur-$TIMESTAMP.sql.gz"
  aws s3 cp "$BACKUP_FILE" "s3://$CENTAUR_S3_BUCKET/$S3_KEY" \
    --endpoint-url "${CENTAUR_S3_ENDPOINT:-https://fsn1.your-objectstorage.com}" \
    --quiet 2>/dev/null && echo "Uploaded to s3://$CENTAUR_S3_BUCKET/$S3_KEY"
fi
