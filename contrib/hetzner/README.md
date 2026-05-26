# Centaur on Hetzner — Per-Customer Deployments

Terraform module and provisioning script for deploying isolated Centaur
instances on Hetzner Cloud. Each customer gets their own k3s cluster,
Postgres, and network — fully isolated from other customers.

## Cost per customer

| Tier | Nodes | Postgres | Monthly |
|------|-------|----------|---------|
| `dev` | 1× CPX32 (4 vCPU, 8 GB) | colocated | ~€24 ($26) |
| `small` | 3× CPX32 (HA) | CCX13 (2 dedicated vCPU) | ~€75 ($82) |
| `prod` | 3× CPX42 (8 vCPU, 16 GB) | CCX23 (4 dedicated vCPU) | ~€125 ($136) |

For reference, the AWS EKS equivalent of `small` costs ~$560/month.

## Prerequisites

```bash
brew install terraform helm kubectl jq
```

You need a Hetzner Cloud API token for each customer project. Create
projects at [console.hetzner.cloud](https://console.hetzner.cloud) and
generate a read/write API token under Security → API Tokens.

Centaur container images must be in a registry the cluster can pull from
(default: `ghcr.io/paradigmxyz`).

## Quick start

```bash
# Set the Hetzner token for the customer's project
export HCLOUD_TOKEN="your-hetzner-api-token"

# Optional: add LLM credentials
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Provision a small production deployment
./provision.sh create acme-corp --tier small --location nbg1

# Check status
./provision.sh status acme-corp

# Get kubeconfig path
export KUBECONFIG=$(./provision.sh kubeconfig acme-corp)
kubectl get pods -n centaur

# Verify
kubectl exec -n centaur deploy/centaur-centaur-api -- \
  curl -s http://localhost:8000/health

# Tear down (destroys everything)
./provision.sh destroy acme-corp
```

## What gets created

```
Hetzner Project (pre-created manually)
├── Private Network (10.0.0.0/16)
├── Firewall (SSH, K8s API, HTTP/S, internal)
├── Load Balancer (LB11, HTTP/HTTPS → nodes)
├── Control Plane nodes (1 or 3, running k3s)
│   └── Centaur namespace
│       ├── centaur-api (FastAPI control plane)
│       ├── centaur-api-proxy (iron-proxy for API)
│       ├── centaur-postgres (StatefulSet, dev tier only)
│       └── sandbox pods (created on demand per conversation)
└── Postgres node (small/prod tiers, dedicated VM + volume)
```

## Tiers

### `dev` — Single node, everything colocated

One CPX32 runs k3s, the Centaur API, Postgres (via the Helm chart's
built-in StatefulSet), and sandbox pods. No HA. Good for testing and
low-traffic customers.

### `small` — 3-node HA with dedicated Postgres

Three CPX32 nodes form an HA k3s cluster. Postgres runs on a separate
CCX13 with a persistent volume. Survives single-node failure.

### `prod` — Larger nodes, ready for burst

Three CPX42 nodes (8 vCPU, 16 GB each) with a CCX23 for Postgres.
More headroom for concurrent sandbox pods.

## Configuration

### Terraform variables

See `variables.tf` for the full list. Key overrides:

```hcl
# terraform.tfvars
customer_id         = "acme-corp"
tier                = "small"
location            = "nbg1"
control_plane_type  = "cpx42"     # override default for tier
postgres_type       = "ccx33"     # bigger Postgres
```

### Adding LLM and tool credentials

After initial provisioning, add secrets to the running cluster:

```bash
export KUBECONFIG=$(./provision.sh kubeconfig acme-corp)

kubectl -n centaur get secret centaur-infra-env -o json | \
  jq --arg key "$(echo -n 'sk-...' | base64)" \
  '.data["OPENAI_API_KEY"]=$key' | kubectl apply -f -

kubectl rollout restart deployment centaur-centaur-api -n centaur
```

### Enabling Slack

```bash
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_SIGNING_SECRET="..."
export SLACKBOT_ENABLED=true
./provision.sh create acme-corp --tier small
```

## Managing deployments

```bash
# List all customer deployments
./provision.sh list

# Check a customer's status
./provision.sh status acme-corp

# Get kubeconfig for kubectl access
export KUBECONFIG=$(./provision.sh kubeconfig acme-corp)

# View logs
kubectl logs -n centaur deploy/centaur-centaur-api --tail=50 -f

# Destroy (interactive confirmation)
./provision.sh destroy acme-corp
```

## State management

Terraform state is stored locally at `~/.centaur/deployments/<customer-id>/`.
For production, configure a remote backend (S3, GCS, Terraform Cloud) in the
Terraform files before provisioning.

## Limitations

- Hetzner Cloud projects must be created manually (no API for project creation)
- No managed Postgres — self-hosted on a dedicated VM or in-cluster
- US regions (ash, hil) have only 1 TB/month included traffic vs 20 TB in EU
- API tokens are binary (read-only or read+write), no fine-grained IAM
- CX and CAX (cheapest) instance types are EU-only
