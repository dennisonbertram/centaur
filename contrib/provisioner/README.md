# Centaur Provisioner Worker

Background service that polls the database for pending deployments and
provisions them on Hetzner Cloud. Runs as a separate Railway service
alongside the dashboard.

## Architecture

```
Dashboard (Next.js on Railway)
  POST /api/deployments → inserts row with status=provisioning
                                         ↓
Database (Railway Postgres)
                                         ↓ polls every 10s
Provisioner (this service on Railway)
  → finds status=provisioning rows
  → runs kubectl/helm to create namespace + deploy Centaur
  → updates row with status=running, ip, apiKey
                                         ↓
Hetzner k3s cluster
  → new namespace with Centaur instance
```

## Modes

### Shared cluster (default, `CENTAUR_PROVISION_MODE=shared`)

All customers run as separate namespaces on one k3s cluster. The provisioner
uses `SHARED_CLUSTER_KUBECONFIG` to create namespaces and deploy Helm releases.

Cost: ~€90/mo for 20-30 customers on an AX102.

### Dedicated VM (`CENTAUR_PROVISION_MODE=dedicated`)

Each customer gets their own Hetzner server via Terraform. The provisioner
uses `HCLOUD_TOKEN` to create servers and deploy k3s.

Cost: €8-125/mo per customer depending on tier.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Railway Postgres connection string |
| `CENTAUR_PROVISION_MODE` | No | `shared` (default) or `dedicated` |
| `POLL_INTERVAL_MS` | No | Polling interval in ms (default: 10000) |
| `SHARED_CLUSTER_KUBECONFIG` | Shared mode | Path to kubeconfig for the shared k3s cluster |
| `SHARED_CLUSTER_IP` | Shared mode | Public IP of the shared cluster |
| `HCLOUD_TOKEN` | Dedicated mode | Hetzner Cloud API token |
| `CENTAUR_IMAGE_REGISTRY` | No | Container registry (default: ghcr.io/paradigmxyz) |
| `CENTAUR_IMAGE_TAG` | No | Image tag (default: latest) |
| `OPENAI_API_KEY` | No | Injected into customer deployments |
| `ANTHROPIC_API_KEY` | No | Injected into customer deployments |

## Development

```bash
cd contrib/provisioner
pnpm install
pnpm dev
```

## Lifecycle

1. User clicks "Create deployment" in the dashboard
2. Dashboard inserts row: `{status: "provisioning", tier: "dev", location: "nbg1"}`
3. Provisioner polls, finds the row
4. In shared mode: creates namespace, K8s secrets, Helm release
5. Updates row: `{status: "running", ip: "...", apiKey: "..."}`
6. Dashboard shows the deployment as running

For destruction:
1. Stripe webhook sets `status: "stopping"` (or user action)
2. Provisioner finds the row, runs `helm uninstall` + `kubectl delete namespace`
3. Updates row: `{status: "stopped"}`
