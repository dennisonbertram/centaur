# Known Gotchas

Hard-won lessons from deploying Centaur-as-a-Service. Every item here caused
a real failure. Read before debugging.

## NetworkPolicy

**Centaur's Helm chart creates default-deny.** Every new capability requires an
explicit NetworkPolicy. These are the ones you'll forget:

| What breaks | Symptom | Fix |
|-------------|---------|-----|
| Sandbox spawn | `Cannot connect to host 10.43.0.1:443` | API pod needs egress to K8s API. **`ipBlock` rules don't work for cluster IPs** — use `namespaceSelector: {}` instead |
| Slack replies | `ECONNREFUSED` in slackbot logs | Slackbot needs egress to `0.0.0.0/0:443` for `api.slack.com` |
| TLS cert issuance | cert-manager challenge returns 502 | Traefik needs ingress to tenant namespace on port 8089 (cert-manager solver) |
| LLM calls | `401 Unauthorized` with placeholder key | iron-proxy MITM is breaking — remove `HTTPS_PROXY` from API and slackbot pods |

**The `HTTPS_PROXY` trap**: The Helm chart sets `HTTPS_PROXY` on API and slackbot
pods to route through iron-proxy. This breaks K8s API calls (TLS MITM rejected)
and Slack WebSocket connections. Fix: remove the env var after Helm deploy.

## Credentials

**The dashboard doesn't push to K8s.** When a user saves a credential in the
dashboard, it goes to the Postgres DB with a `pendingValue`. The provisioner
worker polls for pending credentials and pushes them to the K8s secret. If
the provisioner isn't running, credentials never reach the cluster.

## Agent Browser QA

**`agent-browser` is headless by default.** If you ask a human to complete a
Clerk login, they will not see the window unless you launch with `--headed`:

```bash
AGENT_BROWSER_SESSION_NAME=centaur-dashboard agent-browser --headed open \
  'http://localhost:3058/sign-in?redirect_url=http%3A%2F%2Flocalhost%3A3058%2Fdeployments%2Fnew'
```

After login, verify the protected route and save the state:

```bash
AGENT_BROWSER_SESSION_NAME=centaur-dashboard agent-browser open http://localhost:3058/deployments/new
AGENT_BROWSER_SESSION_NAME=centaur-dashboard agent-browser snapshot -i
mkdir -p .agent-browser
AGENT_BROWSER_SESSION_NAME=centaur-dashboard agent-browser state save .agent-browser/centaur-dashboard-auth.json
```

The saved state contains Clerk session tokens. Keep `.agent-browser/` ignored,
and prefer `AGENT_BROWSER_SESSION_NAME=centaur-dashboard` or
`agent-browser --state .agent-browser/centaur-dashboard-auth.json ...` for
repeatable authenticated dashboard smoke tests.

**Dashboard SQL migrations are not guaranteed to run through Drizzle Kit.**
The dashboard has hand-written SQL files in `contrib/dashboard/drizzle/`. If
the folder has no Drizzle journal metadata for a file, `pnpm exec drizzle-kit
migrate` may not apply it. Missing dashboard migrations show up as protected
page crashes such as `column "inference_mode" does not exist` on `/deployments`
or `relation "api_keys" does not exist` on deployment detail pages. Verify the
target database schema before browser QA and apply the SQL directly if needed.

**Stripe-backed checkout requires local Stripe env.** The Add credits button and
managed-deployment subscription handoff both call `/api/billing/checkout`.
Without Stripe configured, that endpoint returns `503`; the local UI may remain
on the same page without an obvious user-facing explanation.

**Order matters for Slack:**
1. Save Signing Secret in dashboard
2. Wait for provisioner to push it (~15 seconds)
3. THEN set the Request URL in Slack
4. If you set the URL first, the challenge fails because the secret is still `"stub"`

**OpenAI key must be in K8s secret, not just the dashboard.** The sandbox gets
a placeholder from iron-proxy. If the real key isn't in `centaur-infra-env`,
every LLM call fails with `401 Unauthorized: Incorrect API key provided: OPENAI_A**_KEY`.

**Deployment API keys are reveal-once.** The dashboard stores deployment API key
hashes in its `api_keys` table. New plaintext keys live in `pending_value` only
until the provisioner pushes them into `centaur-infra-env` as
`LOCAL_DEV_API_KEY` / `LOCAL_DEV_API_KEYS`; initial keys also use `reveal_value`
so the detail page can show them once. If the provisioner is stopped, newly
created keys appear in the dashboard but will not authenticate against the
tenant API until the worker patches the secret and restarts the API pod.

## DNS

**Namecheap wildcard host must be `*` not `*.domain.com`.** Namecheap appends
the domain automatically. Entering `*.trycentaur.dev` creates
`*.trycentaur.dev.trycentaur.dev`.

**Wildcard DNS takes longer to propagate** than the bare domain — sometimes
5-10 minutes vs 1-2 minutes.

## Images

**Apple Silicon builds don't run on Hetzner.** Always use `--platform linux/amd64`
for Docker builds. The error is `no match for platform in manifest` — not obvious.

**`docker save | ctr import` requires `--all-platforms`.** Without it, the image
index is imported but the platform-specific layers aren't, causing
`ErrImageNeverPull` despite the image appearing in `ctr images ls`.

**`imagePullPolicy: Never` requires exact tag match.** The tag in the Helm values
must exactly match what was imported. `latest` ≠ `amd64` — check with
`k3s crictl images`.

## Helm / k3s

**Postgres service name follows the release name.** A tenant named `acme` gets
`acme-centaur-postgres` as the service name. The `DATABASE_URL` must use this,
not `centaur-centaur-postgres`.

**Traefik is disabled by default in our cloud-init** (`--disable traefik`). It
must be installed separately via Helm for Ingress to work.

**cert-manager is NOT installed by the cloud-init** despite being in the template.
Install it manually: `helm install cert-manager jetstack/cert-manager --set crds.enabled=true`.

## Slack

**Thread replies require @mention.** The bot only responds when directly
mentioned, not on plain thread replies. This is Centaur's default behavior.

**Slack requires HTTPS.** A bare IP address will fail URL verification. You
need a domain + TLS cert.

**Slack sends the verification challenge WITH signature headers.** The slackbot
validates the signature before responding to the challenge. If the Signing
Secret in K8s doesn't match the Slack app's secret, verification fails silently.

## Provisioner

**Railway's Nixpacks ignores `nixpacks.toml` in monorepo contexts.** Use a
Dockerfile instead. Even then, `COPY ../` paths don't work — the build context
is the service directory only.

**The provisioner caches Docker layers.** Code changes that don't modify
`package.json` may not trigger a rebuild. Force with a Dockerfile change.

**`FOR UPDATE SKIP LOCKED` prevents duplicate processing.** Without it, two
worker instances (or a restart overlap) can provision the same tenant twice,
generating different secrets and bricking the deployment.
