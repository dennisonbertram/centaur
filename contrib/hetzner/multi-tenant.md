# Multi-Tenant: Shared Cluster Mode

Instead of one Hetzner VM per customer, run one large server with all customers
as separate Kubernetes namespaces on the same k3s cluster.

## Architecture

```
One AX102 (16-core, 128GB, ~€90/mo)
├── k3s cluster
├── Namespace: centaur-acme
│   ├── centaur-api (Helm release: acme)
│   ├── centaur-postgres (StatefulSet)
│   ├── centaur-api-proxy (iron-proxy)
│   ├── NetworkPolicy (namespace-scoped isolation)
│   └── sandbox pods (on demand)
├── Namespace: centaur-bigcorp
│   ├── centaur-api (Helm release: bigcorp)
│   ├── ...
│   └── sandbox pods
└── Namespace: centaur-startup
    └── ...
```

## Cost comparison

| Model | Per customer | 10 customers | 50 customers |
|-------|-------------|-------------|-------------|
| Dedicated VM (dev) | €8/mo | €80/mo | €400/mo |
| Dedicated VM (small) | €75/mo | €750/mo | €3,750/mo |
| Shared cluster (AX102) | €9/mo* | €90/mo | €90/mo** |

*€90/mo ÷ 10 customers. **Plus additional servers when capacity exceeded.

## Provisioning a tenant on the shared cluster

```bash
# Set the shared cluster's kubeconfig
export KUBECONFIG=~/.centaur/shared-cluster/kubeconfig.yaml

# Create namespace
CUSTOMER=acme
kubectl create namespace "centaur-$CUSTOMER"

# Create secrets
kubectl -n "centaur-$CUSTOMER" create secret generic centaur-infra-env \
  --from-literal=DATABASE_URL="postgresql://..." \
  --from-literal=OPENAI_API_KEY="..." \
  ...

# Deploy Centaur via Helm with namespace isolation
helm upgrade --install "$CUSTOMER" contrib/chart \
  -n "centaur-$CUSTOMER" \
  --set "api.image.repository=ghcr.io/owner/centaur-api" \
  --set "sandbox.image.repository=ghcr.io/owner/centaur-agent" \
  --set "ironProxy.image.repository=ghcr.io/owner/centaur-iron-proxy" \
  --set "ironProxy.secretSource=env" \
  --set "networkPolicy.enabled=true" \
  --set "slackbot.enabled=false" \
  --set "secretManager.backend=env"
```

## Isolation guarantees

- **Network**: Centaur's NetworkPolicy isolates each namespace. Sandbox pods
  can only reach their own iron-proxy and API.
- **Data**: Each namespace has its own Postgres StatefulSet with separate
  PersistentVolumes.
- **Credentials**: Each namespace has its own K8s Secret. iron-proxy injects
  credentials per-namespace.
- **Compute**: Shared CPU/RAM. Use ResourceQuotas per namespace to prevent
  one customer from starving others.

## What you lose vs dedicated VMs

- No hard isolation (a K8s escape affects all tenants)
- Noisy neighbor risk (CPU/RAM contention)
- Shared etcd (K8s API performance under load)
- Single point of failure (if the server goes down, all customers are affected)

## When to use which

- **< 20 customers, cost-sensitive**: Shared cluster on AX102
- **20-100 customers**: Multiple shared clusters (e.g., 3 AX102s, ~20 tenants each)
- **Enterprise/compliance customers**: Dedicated VM per customer
- **Mix**: Put small/dev-tier customers on shared, prod-tier on dedicated
