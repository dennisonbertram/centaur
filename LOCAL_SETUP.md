# Centaur Local Setup Guide

How to get Centaur running locally on macOS with OrbStack.

## Prerequisites

| Tool | Install | Purpose |
|------|---------|---------|
| Docker | OrbStack (recommended) or Docker Desktop | Container runtime |
| Kubernetes | `orbctl start k8s` (OrbStack) or enable in Docker Desktop | Cluster |
| helm | `brew install helm` | Chart deployment |
| just | `brew install just` | Task runner |
| jq | `brew install jq` (usually pre-installed) | JSON parsing |
| kubectl | `brew install kubectl` (bundled with OrbStack) | Cluster management |

## Quick Start (Minimal — No Slack, No 1Password)

This gets the control plane running so you can interact via the API. Agent execution requires LLM credentials (see step 6).

### 1. Clone and enter

```bash
git clone https://github.com/paradigmxyz/centaur.git
cd centaur
```

### 2. Start Kubernetes

```bash
orbctl start k8s
# Verify:
kubectl get nodes
```

### 3. Create secrets

Create the namespace and infra secrets with stub values:

```bash
kubectl create namespace centaur

POSTGRES_PASSWORD="$(openssl rand -hex 32)"
DATABASE_URL="postgresql://tempo:${POSTGRES_PASSWORD}@centaur-centaur-postgres:5432/ai_v2"
LOCAL_DEV_KEY="centaur-local-dev-$(openssl rand -hex 16)"

kubectl -n centaur create secret generic centaur-infra-env \
  --from-literal=IRON_MANAGEMENT_API_KEY="$(openssl rand -hex 32)" \
  --from-literal=SANDBOX_SIGNING_KEY="$(openssl rand -hex 32)" \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --from-literal=LOCAL_DEV_API_KEY="$LOCAL_DEV_KEY" \
  --from-literal=SLACK_BOT_TOKEN="slack-bot-token-stub-not-real" \
  --from-literal=SLACK_SIGNING_SECRET="stub-not-real" \
  --from-literal=SLACKBOT_API_KEY="stub-local-dev-key" \
  --from-literal=OP_SERVICE_ACCOUNT_TOKEN="stub-not-real" \
  --from-literal=OP_VAULT="stub-not-real"

echo "Your local dev API key: $LOCAL_DEV_KEY"
# Save this — you'll need it for API calls.
```

Generate the firewall CA (required by iron-proxy):

```bash
TMPDIR="$(mktemp -d)"
CA_KEY="$TMPDIR/ca-key.pem"
CA_CERT="$TMPDIR/ca-cert.pem"

openssl genrsa -out "$CA_KEY" 4096 >/dev/null 2>&1
openssl req -x509 -new -nodes \
  -key "$CA_KEY" -sha256 -days 3650 \
  -subj "/CN=centaur iron-proxy CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign" \
  -out "$CA_CERT" >/dev/null 2>&1

kubectl -n centaur create secret generic centaur-firewall-ca \
  --from-file=ca-cert.pem="$CA_CERT"
kubectl -n centaur create secret generic centaur-firewall-ca-key \
  --from-file=ca-cert.pem="$CA_CERT" \
  --from-file=ca-key.pem="$CA_KEY"

rm -rf "$TMPDIR"
```

### 4. Build Docker images

```bash
# Build all three images (takes ~5 minutes on first run)
docker build -t centaur-api:latest -f services/api/Dockerfile .
docker build -t centaur-iron-proxy:latest -f services/iron-proxy/Dockerfile .
docker build --target sandbox -t centaur-agent:latest -f services/sandbox/Dockerfile .
```

The sandbox image is ~8GB — it includes Node.js, Python, Bun, Foundry, Claude Code, Codex, and other dev tools.

### 5. Deploy with Helm

Create `values.local.yaml` in the repo root:

```yaml
secretManager:
  backend: env
  envPrefix: ""
  existingSecretName: centaur-infra-env

firewall:
  existingCaSecretName: centaur-firewall-ca
  existingCaKeySecretName: centaur-firewall-ca-key

postgres:
  auth:
    existingSecretName: centaur-infra-env
    existingSecretKey: POSTGRES_PASSWORD
  image:
    pullPolicy: IfNotPresent

slackbot:
  enabled: false

api:
  executionWorkerEnabled: true
  egressDiscovery:
    enabled: false
  image:
    repository: centaur-api
    tag: latest
    pullPolicy: Never

sandbox:
  image:
    repository: centaur-agent
    tag: latest
    pullPolicy: Never

laminar:
  enabled: false

ironProxy:
  image:
    repository: centaur-iron-proxy
    tag: latest
    pullPolicy: Never
  secretSource: env
```

Key differences from the default `values.dev.yaml`:
- `pullPolicy: Never` — uses locally-built images instead of pulling from a registry
- `slackbot.enabled: false` — no Slack app needed
- `ironProxy.secretSource: env` — reads secrets from K8s env vars, not 1Password
- `laminar.enabled: false` — skip observability stack

Deploy:

```bash
helm dependency update contrib/chart
helm upgrade --install centaur contrib/chart -n centaur --create-namespace \
  -f values.local.yaml
```

### 6. Verify

Check pods are running:

```bash
kubectl get pods -n centaur
```

Expected:
```
centaur-api-proxy-...        1/1     Running
centaur-centaur-api-...      1/1     Running
centaur-centaur-postgres-0   1/1     Running
```

Hit the health endpoint:

```bash
kubectl exec -n centaur deploy/centaur-centaur-api -- \
  curl -fsS http://localhost:8000/health
# {"status":"ok"}
```

Test the full agent lifecycle (replace `$LOCAL_DEV_KEY` with your key from step 3):

```bash
# Spawn a sandbox
THREAD_KEY="test-$(date +%s)"
curl_api() {
  kubectl exec -n centaur deploy/centaur-centaur-api -- \
    curl -s "$@" -H "X-Api-Key: $LOCAL_DEV_KEY"
}

SPAWN=$(curl_api -X POST http://localhost:8000/agent/spawn \
  -H "Content-Type: application/json" \
  -d "{\"thread_key\":\"$THREAD_KEY\"}")
echo "$SPAWN" | jq .
GENERATION=$(echo "$SPAWN" | jq -r '.assignment_generation')

# Send a message
curl_api -X POST http://localhost:8000/agent/message \
  -H "Content-Type: application/json" \
  -d "{\"thread_key\":\"$THREAD_KEY\",\"assignment_generation\":$GENERATION,\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"text\":\"Reply with PONG\"}]}" | jq .

# Execute
EXEC=$(curl_api -X POST http://localhost:8000/agent/execute \
  -H "Content-Type: application/json" \
  -d "{\"thread_key\":\"$THREAD_KEY\",\"assignment_generation\":$GENERATION,\"delivery\":{\"platform\":\"dev\"}}")
EXEC_ID=$(echo "$EXEC" | jq -r '.execution_id')

# Check result (poll until completed)
curl_api "http://localhost:8000/agent/executions/$EXEC_ID" | jq .
```

A new sandbox pod will appear in `kubectl get pods -n centaur`. The execution will complete but with an empty result until you add LLM credentials.

### 7. Add LLM credentials (for actual agent execution)

To get agents to actually respond, add your LLM API key to the secret. Check your shell environment first — you may already have keys set:

```bash
env | grep -iE 'OPENAI_API_KEY|ANTHROPIC_API_KEY'
```

Then inject whichever keys you have:

```bash
# For Codex (default harness) — uses OPENAI_API_KEY:
kubectl -n centaur get secret centaur-infra-env -o json | \
  jq --arg key "$(echo -n "$OPENAI_API_KEY" | base64)" \
  '.data["OPENAI_API_KEY"]=$key' | kubectl apply -f -

# For Claude Code harness — uses ANTHROPIC_API_KEY:
kubectl -n centaur get secret centaur-infra-env -o json | \
  jq --arg key "$(echo -n "$ANTHROPIC_API_KEY" | base64)" \
  '.data["ANTHROPIC_API_KEY"]=$key' | kubectl apply -f -

# Restart API to pick up new secrets
kubectl rollout restart deployment centaur-centaur-api -n centaur
```

Then specify harness when spawning: `"harness": "claude"` or `"harness": "codex"`.

## Useful Commands

```bash
# Status
kubectl get pods -n centaur
kubectl get all -n centaur

# Logs
kubectl logs -n centaur deploy/centaur-centaur-api --tail=50 -f
kubectl logs -n centaur <sandbox-pod-name> --tail=50

# Shell into API
kubectl exec -it -n centaur deploy/centaur-centaur-api -- sh

# Teardown
kubectl delete namespace centaur
# Or with just:
just down

# Rebuild and redeploy after code changes
just build-one api
helm upgrade centaur contrib/chart -n centaur -f values.local.yaml
```

## Architecture (what's running)

```
centaur-centaur-postgres    Postgres (ParadeDB) — durable state
centaur-centaur-api         FastAPI control plane — agent lifecycle, tools, workflows
centaur-api-proxy           iron-proxy for the API — credential injection for API's own calls
centaur-centaur-sandbox-*   Per-conversation sandbox pods (created on spawn)
centaur-centaur-proxy-*     Per-sandbox iron-proxy (credential injection for agent calls)
```

## Full Setup (with Slack + 1Password)

For production-like local dev with Slack integration:

1. Create a Slack app at https://api.slack.com/apps
2. Set up 1Password service account
3. Export real credentials:
   ```bash
   export OP_SERVICE_ACCOUNT_TOKEN=...
   export OP_VAULT=...
   export SLACK_BOT_TOKEN=xoxb-...
   export SLACK_SIGNING_SECRET=...
   export SLACKBOT_API_KEY=...
   ```
4. Use the standard flow: `just up`

See the [Quickstart](docs/pages/quickstart.mdx) and [Deploying in Production](docs/pages/deploying-in-production.mdx) docs for details.
