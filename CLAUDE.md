# Centaur-as-a-Service — Product Memory

## What We Are Building

Managed Centaur deployments on Hetzner Cloud (Option B: dedicated deployment per
customer). The customer signs up on a dashboard, picks a tier and region, and
gets an isolated Centaur instance provisioned in 3-5 minutes at 1/7th the cost
of AWS.

## Architecture (Locked for V1)

- **Dashboard**: Next.js 16 + Clerk auth + Drizzle ORM + Railway Postgres
- **Infrastructure**: OpenTofu + Hetzner Cloud + k3s + Centaur Helm chart
- **Provisioning**: `contrib/hetzner/provision.sh` — Terraform apply + kubeconfig fetch + K8s secrets + Helm install + NetworkPolicy fixups
- **Images**: AMD64, built by CI (`.github/workflows/build-images.yaml`), pushed to GHCR
- **Billing**: Stripe (checkout.session.completed triggers provisioning, subscription.deleted triggers teardown)
- **Tool plugin**: Composio integration (upstream PR #180)

## Before You Touch Tenant Infrastructure

Read these before debugging or modifying any tenant deployment:

- `docs/saas/gotchas.md` — known failure modes and their fixes (NetworkPolicy,
  credentials, DNS, images, Slack). Every item caused a real outage.
- `docs/saas/runbook.md` — step-by-step commands for common operations (push
  credentials, fix NetworkPolicy, debug Slack, tear down tenant)
- `docs/saas/setup.md` — full setup guide from zero to working platform
- `contrib/hetzner/TENANT_SETUP.md` — raw notes from the first tenant deployment

If something breaks and you don't find it in the gotchas, add it after fixing.

## Required Task Loop

1. Name the user path being protected.
2. Write the failing test or identify the expected red state.
3. Confirm red before editing implementation.
4. Smallest change to green.
5. `pnpm build` (dashboard) and `tofu validate` (Terraform) before finishing.
6. agent-browser smoke of the real UI — walk it as a naive user.
7. Update docs when behavior changes.

## After Every Task

Run the verification protocol (`.claude/skills/verify-centaur.md`):

1. Type check: `cd contrib/dashboard && npx tsc --noEmit`
2. Build: `pnpm build`
3. Terraform: `cd contrib/hetzner && tofu validate`
4. agent-browser: walk every changed page as a naive user
5. Console errors: `agent-browser errors` — must be empty
6. Report findings as PASS/FAIL/UX

## Project Structure

```
contrib/dashboard/          Next.js management dashboard
  src/app/                  Pages: /, /deployments, /deployments/new, /credentials, /usage
  src/app/api/              API routes: deployments CRUD, credentials, usage, Stripe webhook
  src/lib/                  db.ts (Drizzle + Postgres), schema.ts, stripe.ts
contrib/hetzner/            Terraform module + provisioning
  main.tf                   Servers, network, firewall, LB
  provision.sh              Full lifecycle: create, destroy, status, kubeconfig, list
  k8s-fixups.yaml           NetworkPolicy fixes for k3s
  ops/                      backup.sh, upgrade.sh, monitor.sh, tls-issuer.yaml
contrib/chart/              Centaur Helm chart (upstream)
tools/productivity/composio/ Composio tool plugin
.github/workflows/          CI: build-images.yaml (AMD64, GHCR)
.claude/skills/             verify-centaur.md
```

## Active Test Deployment

- Hetzner server: `178.104.132.172` (CPX22, Nuremberg) — tear down when no longer needed
- Kubeconfig: `~/.centaur/deployments/test-dev/kubeconfig.yaml`
- Dev API key: `centaur-hetzner-dev-61ac82496fc5be8a2ce2195fa59151d0`
- Railway Postgres: `centaur-dashboard` project
- Cost: ~€8/month

## Honest Current State

**Working end-to-end:**
- Terraform provisions Hetzner cluster in ~90 seconds
- Centaur deploys and runs (69 tools, 660 methods)
- Agent execution works (Codex → OpenAI → PONG in 6 seconds)
- Composio tool works (live HN data through Centaur API)
- Dashboard: Clerk auth, all pages render, database connected

**Wired but untested in production:**
- "Create deployment" calls `provisionDeployment()` async — creates DB record immediately, runs Terraform in background, updates status to running/error on completion
- Credentials PUT pushes secrets to K8s via `kubectl patch secret` + `rollout restart`
- Usage page reads from `usage_events` table (empty until Centaur API sends telemetry)
- Stripe webhook triggers provisioning on checkout and destruction on subscription cancel
- All require env vars (HCLOUD_TOKEN, STRIPE_SECRET_KEY, etc.) to function — gracefully degrade when unconfigured

## Explicitly Unacceptable

1. Do not commit secrets or credentials.
2. Do not ship UI changes without agent-browser verification.
3. Do not hand the user a URL without testing it yourself first.
4. Do not add mocks that hide broken real paths.
5. Do not finish with build errors.
