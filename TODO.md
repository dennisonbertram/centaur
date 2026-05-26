# Centaur-as-a-Service — TODO

## Active Infrastructure

- [ ] **Tear down Hetzner test deployment** when no longer needed
  - Server: `178.104.132.172` (CPX22, Nuremberg)
  - LB: `46.225.36.50`
  - Cost: ~€8/month

## Completed

- [x] Fix NetworkPolicy for k3s — `k8s-fixups.yaml` + provision script applies automatically
- [x] SSH key handling — data source lookup, no uniqueness conflicts
- [x] Postgres DATABASE_URL — dev tier uses K8s service name
- [x] Provisioning script — tofu auto-detect, SSH key auto-detect, k8s-fixups, API key generation
- [x] AMD64 CI pipeline — `.github/workflows/build-images.yaml` builds all 4 images for linux/amd64, pushes to GHCR
- [x] Container registry — CI workflow pushes to `ghcr.io/<owner>/centaur-{api,iron-proxy,agent,slackbot}`
- [x] Hetzner project pool — documented in `contrib/hetzner/project-pool.md`
- [x] Composio iron-proxy verification — confirmed SDK sends `x-api-key` to `backend.composio.dev`
- [x] Composio version check — toolkit versions cached with 1hr TTL, falls back to skip on failure
- [x] Composio tool allowlist — `COMPOSIO_ALLOWED_TOOLKITS` env var
- [x] Database — Drizzle ORM + Railway Postgres (serverless-compatible)
- [x] Terraform trigger — `provisionDeployment()` called async from POST /api/deployments, updates DB with IP/status on completion. Stripe webhook calls it on `checkout.session.completed`.
- [x] Credentials backend — PUT /api/deployments/[id]/credentials pushes secrets to K8s cluster via `kubectl patch secret` + `rollout restart`
- [x] Usage metering — server component reads from `usage_events` table aggregated by deployment. POST /api/deployments/[id]/usage ingests events from Centaur API.
- [x] Stripe — `stripe.ts` config (graceful when unconfigured), webhook handles checkout complete (provisions) and subscription deleted (destroys). Metadata carries deployment_id/tier/location.
- [x] TLS — cert-manager installed via cloud-init, Let's Encrypt ClusterIssuer in `ops/tls-issuer.yaml`
- [x] Remote Terraform state — `backend.tf.example` with Hetzner Object Storage, S3, and Terraform Cloud options
- [x] Monitoring — `ops/monitor.sh` checks all deployments, alerts to Slack webhook
- [x] Backups — `ops/backup.sh` pg_dump per customer, 30-day retention, S3 upload
- [x] Upgrades — `ops/upgrade.sh` rolling Helm upgrades with health check
- [x] Multi-region — all 5 locations supported in Terraform with correct network zones
- [x] Rate limiting — per-tier defaults applied via Helm extraEnv in provision.sh (dev: 30 turns/hr, small: 120, prod: 600)
- [x] Token rotation — documented; test token is test-only

## Manual Setup Steps (requires accounts/credentials)

- [ ] Set `HCLOUD_TOKEN` for production Hetzner project
- [ ] Set `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, create Stripe products/prices
- [ ] Create Hetzner project pool (manual via console)
- [ ] Enable GitHub Actions workflow (push to main with `write:packages` scope)
- [ ] Set `CENTAUR_ALERT_SLACK_WEBHOOK` for monitoring alerts
