#!/usr/bin/env bash
# Upgrade Centaur for one or all customer deployments.
# Usage:
#   ./upgrade.sh <customer-id>       # upgrade one customer
#   ./upgrade.sh --all               # upgrade all customers
#   ./upgrade.sh --all --dry-run     # preview what would be upgraded
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
STATE_DIR="${CENTAUR_STATE_DIR:-$HOME/.centaur/deployments}"
DRY_RUN=0

TARGET="${1:?Usage: upgrade.sh <customer-id|--all> [--dry-run]}"
[[ "${2:-}" == "--dry-run" ]] && DRY_RUN=1

upgrade_customer() {
  local cid="$1"
  local dir="$STATE_DIR/$cid"

  if [[ ! -f "$dir/kubeconfig.yaml" ]]; then
    echo "  SKIP $cid: no kubeconfig"
    return
  fi

  export KUBECONFIG="$dir/kubeconfig.yaml"

  if ! kubectl cluster-info >/dev/null 2>&1; then
    echo "  SKIP $cid: cluster unreachable"
    return
  fi

  local current_image
  current_image=$(kubectl get deployment centaur-centaur-api -n centaur \
    -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "unknown")

  echo "  $cid: current=$current_image"

  if [[ $DRY_RUN -eq 1 ]]; then
    echo "  $cid: would upgrade (dry run)"
    return
  fi

  helm dependency update "$REPO_ROOT/contrib/chart" >/dev/null 2>&1

  local registry="${CENTAUR_IMAGE_REGISTRY:-ghcr.io/paradigmxyz}"
  local tag="${CENTAUR_IMAGE_TAG:-latest}"

  helm upgrade centaur "$REPO_ROOT/contrib/chart" \
    -n centaur --reuse-values \
    --set "api.image.repository=${registry}/centaur-api" \
    --set "api.image.tag=$tag" \
    --set "sandbox.image.repository=${registry}/centaur-agent" \
    --set "sandbox.image.tag=$tag" \
    --set "ironProxy.image.repository=${registry}/centaur-iron-proxy" \
    --set "ironProxy.image.tag=$tag" \
    >/dev/null

  kubectl rollout status deployment/centaur-centaur-api -n centaur --timeout=120s >/dev/null

  local health
  health=$(kubectl exec -n centaur deploy/centaur-centaur-api -- \
    curl -s http://localhost:8000/health 2>/dev/null || echo '{"status":"unreachable"}')

  echo "  $cid: upgraded to $tag — health: $health"
}

if [[ "$TARGET" == "--all" ]]; then
  echo "==> Upgrading all deployments"
  for d in "$STATE_DIR"/*/; do
    [[ -d "$d" ]] || continue
    upgrade_customer "$(basename "$d")"
  done
else
  echo "==> Upgrading $TARGET"
  upgrade_customer "$TARGET"
fi
