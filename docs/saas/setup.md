# Centaur-as-a-Service Setup Guide

Complete setup from zero to a working multi-tenant Centaur platform.

## Prerequisites

- Hetzner Cloud account with a project and API token
- Domain with DNS access (e.g. `trycentaur.dev`)
- Railway account (for dashboard + provisioner)
- Clerk account (for user auth)
- OpenAI API key (for the Codex agent harness)

## 1. Infrastructure (one-time)

### Provision the shared k3s cluster

```bash
cd contrib/hetzner
export HCLOUD_TOKEN=your-token
./provision.sh create shared-cluster --tier dev --location nbg1
```

### Install Traefik (Ingress controller)

```bash
export KUBECONFIG=~/.centaur/deployments/shared-cluster/kubeconfig.yaml
helm repo add traefik https://traefik.github.io/charts
helm install traefik traefik/traefik -n kube-system \
  --set "ports.web.hostPort=80" \
  --set "ports.websecure.hostPort=443" \
  --set "securityContext.runAsNonRoot=false" \
  --set "securityContext.runAsUser=0" \
  --set "service.type=ClusterIP"
```

### Install cert-manager (TLS certificates)

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true --wait

kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: traefik
EOF
```

### Load Centaur images (AMD64)

```bash
# Build on Apple Silicon for AMD64
docker buildx build --platform linux/amd64 --load -t centaur-api:amd64 -f services/api/Dockerfile .
docker buildx build --platform linux/amd64 --load -t centaur-iron-proxy:amd64 -f services/iron-proxy/Dockerfile .
docker buildx build --platform linux/amd64 --load -t centaur-slackbot:amd64 -f services/slackbot/Dockerfile .
docker buildx build --platform linux/amd64 --load --target sandbox -t centaur-agent:amd64 -f services/sandbox/Dockerfile .

# Push to the server
for img in centaur-api centaur-iron-proxy centaur-slackbot centaur-agent; do
  docker save $img:amd64 | ssh root@SERVER_IP "ctr -n k8s.io images import --all-platforms -"
done
```

## 2. DNS

Point your domain at the cluster IP:

| Type | Host | Value |
|------|------|-------|
| A | `@` | `SERVER_IP` |
| A | `*` | `SERVER_IP` |

**Namecheap note**: wildcard host must be `*` not `*.domain.com`.

## 3. Railway services

### Dashboard

```bash
cd contrib/dashboard
railway init --name centaur-dashboard
railway add --database postgres
railway add --service dashboard
railway link --service dashboard
railway variables --set "DATABASE_URL=\${{Postgres.DATABASE_URL}}"
railway variables --set "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_..."
railway variables --set "CLERK_SECRET_KEY=sk_..."
railway up --detach
railway domain  # generates public URL
```

### Provisioner worker

```bash
cd contrib/provisioner
railway add --service provisioner
railway link --service provisioner
railway variables --set "DATABASE_URL=\${{Postgres.DATABASE_URL}}"
railway variables --set "CENTAUR_PROVISION_MODE=shared"
railway variables --set "CENTAUR_DOMAIN=trycentaur.dev"
railway variables --set "SHARED_CLUSTER_KUBECONFIG_B64=$(cat ~/.centaur/deployments/shared-cluster/kubeconfig.yaml | base64 | tr -d '\n')"
railway variables --set "SHARED_CLUSTER_IP=SERVER_IP"
railway variables --set "HCLOUD_TOKEN=your-token"
railway variables --set "OPENAI_API_KEY=sk-..."  # injected into every tenant
railway up --detach
```

## 4. Push DB schema

```bash
cd contrib/dashboard
DATABASE_URL="your-railway-postgres-url" npx drizzle-kit push
```

## 5. Test the flow

1. Open the dashboard URL
2. Sign in via Clerk
3. Create a deployment
4. Watch the provisioner logs: `railway logs` (linked to provisioner)
5. Deployment should go from `provisioning` → `running` in ~30 seconds
6. Click into the deployment → add OpenAI key
7. Wait ~15 seconds for the provisioner to push the credential
8. Set up Slack app (follow the wizard instructions)
9. Mention the bot in Slack → it should respond

## What the provisioner does per tenant

1. Creates namespace `centaur-{name}`
2. Generates secrets (Postgres password, CA certs, API key) — idempotent on retry
3. Deploys Centaur via Helm
4. Creates Ingress with TLS (`{slug}.trycentaur.dev`)
5. Applies NetworkPolicies (Traefik, K8s API, slackbot egress)
6. Removes `HTTPS_PROXY` from API and slackbot
7. Waits for API rollout
8. Updates DB with status, IP, webhook URL, API key

See `docs/saas/gotchas.md` for everything that can go wrong.
