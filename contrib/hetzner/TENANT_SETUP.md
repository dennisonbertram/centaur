# Tenant Setup Gotchas

Everything that went wrong while setting up the first tenant deployment, and
how to avoid it next time. These fixes need to be baked into the provisioner.

## NetworkPolicy fixes required per tenant

Centaur's Helm chart creates a default-deny NetworkPolicy per namespace. Several
additional policies are needed for a tenant to function:

### 1. DNS (already in chart)
The chart creates `{release}-centaur-allow-dns` which allows all pods to reach
CoreDNS on port 53. This works.

### 2. Traefik Ingress access
Traefik runs in `kube-system`. Tenant pods need to accept traffic from it.

```yaml
# Ports: 8000 (API), 3001 (slackbot), 8089 (cert-manager solver)
allow-traefik-ingress:
  podSelector: {}
  ingress from: kube-system namespace
  ports: 8000, 3001, 8089
```

### 3. API → K8s API server
The Centaur API calls the K8s API (`10.43.0.1:443`) to spawn sandbox pods.
`ipBlock` rules do NOT work for cluster service IPs (they're virtual). Use
`namespaceSelector: {}` to allow egress to all namespaces on port 443.

```yaml
api-k8s-access:
  podSelector: app.kubernetes.io/component=api
  egress to: all namespaces on 443, all IPs on 443
```

### 4. Slackbot → internet
The slackbot calls `api.slack.com:443` to send messages. Without this, it
receives events but can't reply (`ECONNREFUSED`).

```yaml
slackbot-egress-internet:
  podSelector: app.kubernetes.io/component=slackbot
  egress to: 0.0.0.0/0 on 443
```

### 5. Remove HTTPS_PROXY from API and slackbot
The Helm chart injects `HTTPS_PROXY` env vars that route traffic through
iron-proxy. This breaks:
- API → K8s API (iron-proxy does TLS MITM which K8s rejects)
- Slackbot → Slack API (iron-proxy can't proxy WebSocket)

Fix: `kubectl set env deployment/{name}-centaur-api --containers=api HTTPS_PROXY- HTTP_PROXY- https_proxy- http_proxy-`
Same for slackbot.

## Credential push pipeline

Dashboard saves credentials but can't push to K8s (no kubectl access).
The provisioner worker polls for `credentials.pendingValue IS NOT NULL` and:
1. Patches the K8s secret with `kubectl patch secret centaur-infra-env`
2. Restarts slackbot and API deployments
3. Clears `pendingValue`

**Critical**: Without this, saved credentials stay in the dashboard DB but
never reach the running Centaur instance.

## Ingress setup per tenant

Each tenant needs:
1. An Ingress resource in their namespace routing:
   - `/api/webhooks/slack` → slackbot service (port 3001)
   - `/api/slack/*` → slackbot service (port 3001)
   - `/` → API service (port 8000)
2. TLS via cert-manager (`cert-manager.io/cluster-issuer: letsencrypt-prod`)
3. Host: `{slug}.trycentaur.dev`

The cert-manager HTTP-01 solver needs port 8089 allowed through the Traefik
NetworkPolicy (listed above).

## DNS requirements

- `*.trycentaur.dev` → A record → cluster IP
- `trycentaur.dev` → A record → cluster IP
- On Namecheap: the wildcard host must be `*` not `*.trycentaur.dev`

## Image requirements

- All images must be AMD64 (Hetzner servers are x86)
- Images: centaur-api, centaur-iron-proxy, centaur-agent, centaur-slackbot
- Use `pullPolicy: Never` when images are pre-loaded on the server
- Use `docker save | ssh | ctr import --all-platforms` to load images

## OpenAI key injection

The Codex harness in the sandbox receives a placeholder `OPENAI_API_KEY`.
iron-proxy replaces it on outbound requests to `api.openai.com`. But:
- The key must be in the `centaur-infra-env` K8s secret
- The provisioner must have `OPENAI_API_KEY` in its env to inject at provision time
- OR the credential push pipeline must deliver it after provisioning

## Slack setup order

1. User creates Slack app, gets Bot Token + Signing Secret
2. User saves both in the dashboard
3. Provisioner pushes to K8s secret, restarts slackbot
4. User sets Request URL in Slack (`https://{slug}.trycentaur.dev/api/webhooks/slack`)
5. Slack sends verification challenge → slackbot verifies signature → responds with challenge
6. User subscribes to bot events
7. User mentions bot in a channel → Centaur responds

**Thread replies require @mention** — the bot only responds when directly mentioned,
not on plain thread replies.
