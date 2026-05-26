#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Centaur customer provisioning script
#
# Usage:
#   ./provision.sh create <customer-id> [--tier dev|small|prod] [--location nbg1]
#   ./provision.sh destroy <customer-id>
#   ./provision.sh status <customer-id>
#   ./provision.sh kubeconfig <customer-id>
#   ./provision.sh list
#
# Requires: tofu (or terraform), helm, kubectl, jq, ssh
#
# Environment:
#   HCLOUD_TOKEN           — Hetzner API token for the customer's project
#   CENTAUR_IMAGE_REGISTRY — Container registry (default: ghcr.io/paradigmxyz)
#   CENTAUR_IMAGE_TAG      — Image tag (default: latest)
#   SLACK_BOT_TOKEN        — (optional) Slack bot token
#   SLACK_SIGNING_SECRET   — (optional) Slack signing secret
#   OPENAI_API_KEY         — (optional) For Codex harness
#   ANTHROPIC_API_KEY      — (optional) For Claude harness
#   COMPOSIO_API_KEY       — (optional) For Composio tool
# ------------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
STATE_DIR="${CENTAUR_STATE_DIR:-$HOME/.centaur/deployments}"

# Prefer tofu (OpenTofu) over terraform
TF="$(command -v tofu 2>/dev/null || command -v terraform 2>/dev/null || true)"
if [[ -z "$TF" ]]; then
  echo "FATAL: tofu or terraform is required" >&2
  exit 1
fi

usage() {
  sed -n '3,14p' "$0" | sed 's/^# //' | sed 's/^#//'
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "FATAL: $1 is required" >&2; exit 1; }
}

require_cmd helm
require_cmd kubectl
require_cmd jq
require_cmd ssh

COMMAND="${1:-}"
CUSTOMER_ID="${2:-}"
TIER="small"
LOCATION="nbg1"

shift 2 2>/dev/null || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tier)     TIER="${2:?--tier requires a value}"; shift 2 ;;
    --location) LOCATION="${2:?--location requires a value}"; shift 2 ;;
    *)          echo "Unknown arg: $1" >&2; usage ;;
  esac
done

customer_dir() {
  echo "$STATE_DIR/$1"
}

# --- CREATE ---

cmd_create() {
  local cid="$1"
  local dir
  dir="$(customer_dir "$cid")"

  if [[ -z "${HCLOUD_TOKEN:-}" ]]; then
    echo "FATAL: HCLOUD_TOKEN is required" >&2
    exit 1
  fi

  echo "==> Provisioning Centaur for customer: $cid (tier=$TIER, location=$LOCATION)"

  mkdir -p "$dir"

  # Copy Terraform files and templates
  cp "$SCRIPT_DIR"/*.tf "$dir/"
  cp "$SCRIPT_DIR"/*.tftpl "$dir/"

  # Create tfvars
  local ssh_key_var="[]"
  if [[ -f "$HOME/.ssh/id_rsa.pub" ]]; then
    ssh_key_var="[\"$(cat "$HOME/.ssh/id_rsa.pub")\"]"
  elif [[ -f "$HOME/.ssh/id_ed25519.pub" ]]; then
    ssh_key_var="[\"$(cat "$HOME/.ssh/id_ed25519.pub")\"]"
  fi

  cat > "$dir/terraform.tfvars" <<TFVARS
customer_id    = "$cid"
tier           = "$TIER"
location       = "$LOCATION"
hcloud_token   = "$HCLOUD_TOKEN"
ssh_public_keys = $ssh_key_var
TFVARS

  # Add optional secrets to tfvars
  [[ -n "${SLACK_BOT_TOKEN:-}" ]]      && echo "slack_bot_token      = \"$SLACK_BOT_TOKEN\""      >> "$dir/terraform.tfvars"
  [[ -n "${SLACK_SIGNING_SECRET:-}" ]]  && echo "slack_signing_secret  = \"$SLACK_SIGNING_SECRET\""  >> "$dir/terraform.tfvars"
  [[ -n "${OPENAI_API_KEY:-}" ]]        && echo "openai_api_key        = \"$OPENAI_API_KEY\""        >> "$dir/terraform.tfvars"
  [[ -n "${ANTHROPIC_API_KEY:-}" ]]     && echo "anthropic_api_key     = \"$ANTHROPIC_API_KEY\""     >> "$dir/terraform.tfvars"
  [[ -n "${CENTAUR_IMAGE_REGISTRY:-}" ]] && echo "centaur_image_registry = \"$CENTAUR_IMAGE_REGISTRY\"" >> "$dir/terraform.tfvars"
  [[ -n "${CENTAUR_IMAGE_TAG:-}" ]]      && echo "centaur_image_tag      = \"$CENTAUR_IMAGE_TAG\""      >> "$dir/terraform.tfvars"

  echo "  [1/5] Running Terraform..."
  (cd "$dir" && "$TF" init -input=false -no-color >/dev/null 2>&1)
  (cd "$dir" && "$TF" apply -auto-approve -input=false -no-color)

  echo "  [2/5] Fetching kubeconfig..."
  local cp_ip
  cp_ip="$(cd "$dir" && "$TF" output -raw init_node_ip)"

  echo "    Waiting for k3s on $cp_ip..."
  for _ in $(seq 1 90); do
    if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "root@$cp_ip" \
      "test -f /etc/rancher/k3s/k3s.yaml && kubectl get nodes 2>/dev/null | grep -q Ready" 2>/dev/null; then
      break
    fi
    sleep 5
  done

  ssh -o StrictHostKeyChecking=no "root@$cp_ip" cat /etc/rancher/k3s/k3s.yaml \
    | sed "s/127.0.0.1/$cp_ip/" \
    > "$dir/kubeconfig.yaml"

  export KUBECONFIG="$dir/kubeconfig.yaml"

  echo "  [3/5] Creating Kubernetes secrets..."
  local pg_pass iron_key sandbox_key slackbot_key db_url ca_cert ca_key
  pg_pass="$(cd "$dir" && "$TF" output -raw postgres_password)"
  iron_key="$(cd "$dir" && "$TF" output -raw iron_management_key)"
  sandbox_key="$(cd "$dir" && "$TF" output -raw sandbox_signing_key)"
  slackbot_key="$(cd "$dir" && "$TF" output -raw slackbot_api_key)"
  db_url="$(cd "$dir" && "$TF" output -raw database_url)"
  ca_cert="$(cd "$dir" && "$TF" output -raw ca_cert_pem)"
  ca_key="$(cd "$dir" && "$TF" output -raw ca_key_pem)"

  local dev_api_key="centaur-${cid}-$(openssl rand -hex 16)"

  kubectl create namespace centaur --dry-run=client -o yaml | kubectl apply -f - >/dev/null

  local secret_args=(
    -n centaur create secret generic centaur-infra-env
    --from-literal=POSTGRES_PASSWORD="$pg_pass"
    --from-literal=DATABASE_URL="$db_url"
    --from-literal=IRON_MANAGEMENT_API_KEY="$iron_key"
    --from-literal=SANDBOX_SIGNING_KEY="$sandbox_key"
    --from-literal=SLACKBOT_API_KEY="$slackbot_key"
    --from-literal=LOCAL_DEV_API_KEY="$dev_api_key"
    --from-literal=SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN:-stub}"
    --from-literal=SLACK_SIGNING_SECRET="${SLACK_SIGNING_SECRET:-stub}"
    --from-literal=OP_SERVICE_ACCOUNT_TOKEN="unused-env-mode"
    --from-literal=OP_VAULT="unused-env-mode"
  )
  [[ -n "${OPENAI_API_KEY:-}" ]]    && secret_args+=(--from-literal=OPENAI_API_KEY="$OPENAI_API_KEY")
  [[ -n "${ANTHROPIC_API_KEY:-}" ]] && secret_args+=(--from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY")
  [[ -n "${COMPOSIO_API_KEY:-}" ]]  && secret_args+=(--from-literal=COMPOSIO_API_KEY="$COMPOSIO_API_KEY")
  kubectl "${secret_args[@]}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

  kubectl -n centaur create secret generic centaur-firewall-ca \
    --from-literal=ca-cert.pem="$ca_cert" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  kubectl -n centaur create secret generic centaur-firewall-ca-key \
    --from-literal=ca-cert.pem="$ca_cert" \
    --from-literal=ca-key.pem="$ca_key" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null

  echo "  [4/5] Deploying Centaur via Helm..."

  local registry="${CENTAUR_IMAGE_REGISTRY:-ghcr.io/paradigmxyz}"
  local tag="${CENTAUR_IMAGE_TAG:-latest}"
  local pull_policy="${CENTAUR_IMAGE_PULL_POLICY:-Always}"

  helm dependency update "$REPO_ROOT/contrib/chart" >/dev/null 2>&1

  helm upgrade --install centaur "$REPO_ROOT/contrib/chart" \
    -n centaur --create-namespace \
    --set "api.image.repository=${registry}/centaur-api" \
    --set "api.image.tag=$tag" \
    --set "api.image.pullPolicy=$pull_policy" \
    --set "api.executionWorkerEnabled=true" \
    --set "api.egressDiscovery.enabled=false" \
    --set "sandbox.image.repository=${registry}/centaur-agent" \
    --set "sandbox.image.tag=$tag" \
    --set "sandbox.image.pullPolicy=$pull_policy" \
    --set "ironProxy.image.repository=${registry}/centaur-iron-proxy" \
    --set "ironProxy.image.tag=$tag" \
    --set "ironProxy.image.pullPolicy=$pull_policy" \
    --set "ironProxy.secretSource=env" \
    --set "slackbot.enabled=${SLACKBOT_ENABLED:-false}" \
    --set "slackbot.image.repository=${registry}/centaur-slackbot" \
    --set "slackbot.image.tag=$tag" \
    --set "laminar.enabled=false" \
    --set "secretManager.backend=env" \
    --set "networkPolicy.enabled=true" \
    --set "api.extraEnv.RATE_LIMIT_AGENT_TURNS_PER_HOUR=$(case $TIER in dev) echo 30;; small) echo 120;; prod) echo 600;; esac)" \
    --set "api.extraEnv.RATE_LIMIT_SANDBOX_CONCURRENT=$(case $TIER in dev) echo 2;; small) echo 10;; prod) echo 50;; esac)" \
    --set "api.extraEnv.RATE_LIMIT_TOOL_CALLS_PER_HOUR=$(case $TIER in dev) echo 100;; small) echo 600;; prod) echo 3000;; esac)" \
    >/dev/null

  echo "  [5/5] Applying k3s NetworkPolicy fixups..."
  kubectl apply -f "$SCRIPT_DIR/k8s-fixups.yaml" >/dev/null

  # Remove HTTPS_PROXY from the API pod so the K8s client can reach the
  # API server directly. aiohttp doesn't respect NO_PROXY for IP addresses.
  kubectl set env deployment/centaur-centaur-api -n centaur \
    --containers=api HTTPS_PROXY- HTTP_PROXY- https_proxy- http_proxy- \
    2>/dev/null || true

  kubectl rollout status deployment/centaur-centaur-api -n centaur --timeout=120s >/dev/null 2>&1

  echo ""
  echo "==> Centaur deployed for customer: $cid"
  echo "    Tier:           $TIER"
  echo "    Location:       $LOCATION"
  echo "    Load Balancer:  $(cd "$dir" && "$TF" output -raw load_balancer_ip)"
  echo "    API Key:        $dev_api_key"
  echo "    Kubeconfig:     $dir/kubeconfig.yaml"
  echo "    Cost estimate:  $(cd "$dir" && "$TF" output -raw monthly_cost_estimate)"
  echo ""
  echo "    Health check:"
  echo "      KUBECONFIG=$dir/kubeconfig.yaml kubectl exec -n centaur deploy/centaur-centaur-api -- curl -s http://localhost:8000/health"
}

# --- DESTROY ---

cmd_destroy() {
  local cid="$1"
  local dir
  dir="$(customer_dir "$cid")"

  if [[ ! -d "$dir" ]]; then
    echo "No deployment found for customer: $cid" >&2
    exit 1
  fi

  if [[ -z "${HCLOUD_TOKEN:-}" ]]; then
    echo "FATAL: HCLOUD_TOKEN is required for destroy" >&2
    exit 1
  fi

  echo "==> Destroying Centaur deployment for customer: $cid"
  read -r -p "    Are you sure? This deletes all data. [y/N] " confirm
  if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Aborted."
    exit 0
  fi

  (cd "$dir" && "$TF" destroy -auto-approve -input=false)
  rm -rf "$dir"
  echo "==> Destroyed deployment for: $cid"
}

# --- STATUS ---

cmd_status() {
  local cid="$1"
  local dir
  dir="$(customer_dir "$cid")"

  if [[ ! -d "$dir" ]]; then
    echo "No deployment found for customer: $cid" >&2
    exit 1
  fi

  export KUBECONFIG="$dir/kubeconfig.yaml"

  echo "==> Customer: $cid"
  echo "    Tier:          $(cd "$dir" && "$TF" output -raw tier 2>/dev/null || echo '?')"
  echo "    Load Balancer: $(cd "$dir" && "$TF" output -raw load_balancer_ip 2>/dev/null || echo '?')"
  echo "    Cost estimate: $(cd "$dir" && "$TF" output -raw monthly_cost_estimate 2>/dev/null || echo '?')"
  echo ""

  if kubectl cluster-info >/dev/null 2>&1; then
    echo "    Pods:"
    kubectl get pods -n centaur --no-headers 2>/dev/null | sed 's/^/      /'
    echo ""
    echo "    Health: $(kubectl exec -n centaur deploy/centaur-centaur-api -- curl -s http://localhost:8000/health 2>/dev/null || echo 'unreachable')"
  else
    echo "    Cluster: unreachable"
  fi
}

# --- KUBECONFIG ---

cmd_kubeconfig() {
  local cid="$1"
  local dir
  dir="$(customer_dir "$cid")"

  if [[ ! -f "$dir/kubeconfig.yaml" ]]; then
    echo "No kubeconfig found for customer: $cid" >&2
    exit 1
  fi

  echo "$dir/kubeconfig.yaml"
}

# --- LIST ---

cmd_list() {
  if [[ ! -d "$STATE_DIR" ]]; then
    echo "No deployments found."
    return
  fi

  printf "%-20s %-8s %-10s %s\n" "CUSTOMER" "TIER" "LOCATION" "COST"
  for d in "$STATE_DIR"/*/; do
    [[ -d "$d" ]] || continue
    local cid
    cid="$(basename "$d")"
    local tier cost
    tier="$(cd "$d" && "$TF" output -raw tier 2>/dev/null || echo "?")"
    cost="$(cd "$d" && "$TF" output -raw monthly_cost_estimate 2>/dev/null || echo "?")"
    printf "%-20s %-8s %-10s %s\n" "$cid" "$tier" "" "$cost"
  done
}

# --- Dispatch ---

case "$COMMAND" in
  create)    [[ -n "$CUSTOMER_ID" ]] || usage; cmd_create "$CUSTOMER_ID" ;;
  destroy)   [[ -n "$CUSTOMER_ID" ]] || usage; cmd_destroy "$CUSTOMER_ID" ;;
  status)    [[ -n "$CUSTOMER_ID" ]] || usage; cmd_status "$CUSTOMER_ID" ;;
  kubeconfig) [[ -n "$CUSTOMER_ID" ]] || usage; cmd_kubeconfig "$CUSTOMER_ID" ;;
  list)      cmd_list ;;
  *)         usage ;;
esac
