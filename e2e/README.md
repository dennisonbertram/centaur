# Centaur E2E Tests

This directory contains service-neutral system tests for the Centaur stack.
The tests talk to a real API deployment, which creates real sandbox pods and
drives a real harness. They intentionally do not live under `services/api` or
`services/slackbot` because they validate product-level behavior across
multiple services.

## Run against an existing local stack

Bring Centaur up first, then run the E2E package:

```bash
just up
pnpm install
CENTAUR_API_URL=http://localhost:8000 \
SLACKBOT_API_KEY=<your-local-slackbot-api-key> \
pnpm --filter @centaur/e2e test
```

If the API is only reachable from inside Kubernetes, port-forward it first:

```bash
kubectl port-forward -n centaur deploy/centaur-centaur-api 8000:8000
```

## Run in an ephemeral kind cluster

The easiest local end-to-end path is to let the helper create a disposable
kind cluster, build and load local images, deploy Centaur, run the tests, then
delete the cluster. The E2E deployment enables a small warm pool and waits for
two warm sandboxes before starting tests:

```bash
AMP_API_KEY=... e2e/deploy/run-kind.sh
```

Useful options:

```bash
# Reuse already-built local images
AMP_API_KEY=... E2E_BUILD=0 e2e/deploy/run-kind.sh

# Keep the cluster after the run for debugging
AMP_API_KEY=... CENTAUR_E2E_KEEP_CLUSTER=1 e2e/deploy/run-kind.sh

# Use a different kind cluster name
AMP_API_KEY=... CENTAUR_E2E_KIND_CLUSTER=my-centaur-e2e e2e/deploy/run-kind.sh
```

## CI

`.github/workflows/e2e-amp.yml` runs the same tests in kind. It requires the
GitHub Actions secret `AMP_API_KEY`.
