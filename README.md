# Paradigm AI v2

Internal AI platform: agent sandbox, 80+ tools, and Slack integration.
FastAPI backend, Docker sandboxes, mitmproxy firewall, Postgres+pgvector.

## Architecture

```
┌─ default ──────────────────────────────────────────────────────────────────┐
│                                                                            │
│  nginx :8000          auth :4000                                           │
│  reverse proxy        HMAC session cookie                                  │
│  auth_request gate                                                         │
│                                                                            │
│  ┌─ app_net (internal) ─────────────────────────────────────────────────┐  │
│  │                                                                      │  │
│  │  api :8000           slackbot :3001         web :3001                │  │
│  │  FastAPI             Next.js Bolt           Next.js thread viewer    │  │
│  │  tools run in-proc   Slack events           UI for conversations    │  │
│  │                                                                      │  │
│  │  ┌─ data_net (internal) ──────────────────────────────────────────┐  │  │
│  │  │                                                                │  │  │
│  │  │  pgbouncer          postgres :5432         redis               │  │  │
│  │  │  conn pooler        pgvector               cache               │  │  │
│  │  │                                                                │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ agent_net (internal) ───────────────────────────────────────────────┐  │
│  │                                                                      │  │
│  │  sandbox (agent2:latest)         firewall :8080                      │  │
│  │  amp / claude / codex            mitmproxy — credential injection    │  │
│  │  1 container per Slack thread    replaces stubs with real secrets    │  │
│  │                                                                      │  │
│  │  sandbox ──HTTPS_PROXY──► firewall ──► internet                     │  │
│  │  sandbox ──REST /tools/*──► api                                     │  │
│  │                                                                      │  │
│  │  api (also on agent_net — spawns + communicates with sandboxes)      │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ control_net (internal) ─── api + firewall ONLY ─────────────────────┐ │
│  │  firewall ──GET /internal/injection-map──► api  (refreshed q60s)     │ │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ obs_net (internal) ─────────────────────────────────────────────────┐ │
│  │  grafana    prometheus    victorialogs    promtail                    │ │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

┌─ secrets_net (internal) ─── firewall + secrets ONLY ───────────────────────┐
│                                                                             │
│  firewall ──GET /secrets/{key}──► secrets :8100 (1Password cache, 30s TTL) │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ secrets_egress ─── secrets ONLY (outbound internet) ──────────────────────┐
│                                                                             │
│  secrets ──────────────────────► 1password.com (SDK API)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key isolation:**
- Sandboxes **cannot** reach Postgres, Redis, or the secret manager
- Secret manager is **only** reachable by the firewall (`secrets_net`)
- Injection map is **only** reachable by the firewall (`control_net`)
- No container spans all networks

1 Slack thread = 1 Docker container. The API spawns sibling containers
running harness CLIs (amp, claude-code, codex). Inside the container,
the harness calls back to the API via REST for tool calls, search, etc.

## Security Architecture

> **Cardinal rule: no service except the secret manager and firewall ever touches a real secret.**

### Threat Model

AI agents execute arbitrary code in sandboxes. A compromised sandbox must not be able to:
1. Read real API keys from its environment or memory
2. Exfiltrate credentials to attacker-controlled domains
3. Access internal services (Postgres, secret manager, admin endpoints)
4. Escape to the host or other containers

### Secret Flow: Placeholder Injection

Real secrets live **only** in the secret manager (1Password cache) and are fetched
**only** by the firewall. Every other service uses placeholder strings.

```
Tool declares:     secrets = ["ALCHEMY_API_KEY"]       (in pyproject.toml)
                   hosts   = ["*.alchemy.com"]

Container gets:    ALCHEMY_API_KEY=ALCHEMY_API_KEY     ← stub, not real

Tool code:         headers = {"X-API-Key": secret("ALCHEMY_API_KEY")}
                   # secret() returns "ALCHEMY_API_KEY" (the stub string)

Outbound request:  X-API-Key: ALCHEMY_API_KEY
                         │
                         ▼  HTTPS_PROXY → firewall (mitmproxy)
                         │
                         │  1. Lookup injection map: ALCHEMY_API_KEY allowed for *.alchemy.com? ✓
                         │  2. Fetch real key from secret manager
                         │  3. Replace stub in header with real key
                         │
                         ▼  To alchemy.com:
                   X-API-Key: sk-real-alchemy-key-...
```

If a stub is sent to an unauthorized host, the firewall **strips the header**
and logs `exfil_attempt`. The agent never sees the real key.

### ⚠️  Security Invariants — Do Not Violate

These are the rules. If a change breaks any of these, it is a security regression.

| # | Invariant | Enforcement |
|---|-----------|-------------|
| **S1** | **The API, slackbot, web, and auth containers never have real tool/API secrets in their environment.** Tool secrets exist only in the secret manager and are injected in-flight by the firewall. | `secret()` returns stub values (key name = value). No `EnvBackend` fallback. |
| **S2** | **All outbound HTTPS from the API and sandboxes routes through the firewall** (`HTTPS_PROXY=http://firewall:8080`). This is how stubs get replaced with real credentials. | `docker-compose.yml` sets `HTTPS_PROXY` on api and sandbox containers. |
| **S3** | **Internal service-to-service calls bypass the proxy.** Plain HTTP calls between containers (api→slackbot, api→pgbouncer, etc.) must NOT route through the firewall. | `NO_PROXY` lists all internal hostnames. All internal calls use `http://` not `https://`. |
| **S4** | **The secret manager is reachable only by the firewall.** No other service can query `/secrets/*`. | `secrets_net` is an internal Docker network with only `secrets` + `firewall` as members. |
| **S5** | **The injection map controls which secrets can go to which hosts.** A tool declaring `hosts=["*.alchemy.com"]` and `secrets=["ALCHEMY_API_KEY"]` means only `ALCHEMY_API_KEY` can be injected into requests to `*.alchemy.com`. | `GET /internal/injection-map` on `control_net` (api + firewall only). Firewall refreshes every 60s. |
| **S6** | **Sandboxes never get the root API key.** The API mints short-lived, scoped `sbx1.*` tokens with `["agent", "tools:*"]` scope. If minting fails, the container must not start. | `mint_sandbox_token()` in `deps.py`. No fallback to root key. |
| **S7** | **Catch-all host patterns are rejected.** Tools cannot declare `hosts = ["*"]`, `["*.com"]`, or IP addresses. | Validation in `_collect_tools()`. |
| **S8** | **The firewall blocks SSRF.** Destination hostnames are resolved and blocked if they point to private/internal IPs. Redirects to internal IPs are also blocked. | `_is_blocked_host()` in `addon.py`. |
| **S9** | **Response bodies from LLM providers are scanned for leaked secrets.** If a real secret value appears in a response, it is redacted to `[REDACTED:KEY_NAME]` before reaching the sandbox. | `_scan_response_body()` in `addon.py`. |
| **S10** | **Non-allowlisted hosts are restricted to safe HTTP methods** (GET, HEAD, OPTIONS). Only LLM API hosts and tool-declared hosts allow POST/PUT/DELETE. | Method filtering in `addon.py`. |

### Network Isolation

```
  secrets_net (internal)      secrets + firewall only
  secrets_egress              secrets only (outbound internet for 1Password SDK)
  control_net (internal)      api + firewall (injection map endpoint)
  agent_net (internal)        api + firewall + sandbox containers
  app_net (internal)          api + slackbot + web (inter-service calls)
  data_net (internal)         api + slackbot + web + pgbouncer + postgres + redis
  obs_net (internal)          nginx + grafana + prometheus + victorialogs + promtail
  default                     nginx, api, slackbot, web, auth, grafana
```

No container spans all networks. The secret manager cannot reach Postgres.
Sandboxes cannot reach Postgres, Redis, or the secret manager.

### Bootstrap Secrets

Some secrets cannot be injected by the firewall because they are needed for
inbound authentication or to start the security chain itself. These are
injected by CI (GitHub Actions) as environment variables:

| Secret | Container | Purpose |
|--------|-----------|---------|
| `OP_SERVICE_ACCOUNT_TOKEN` | secrets | 1Password SDK access |
| `SECRET_MANAGER_TOKEN` | firewall | Auth to secret manager HTTP API |
| `API_SECRET_KEY` | api, auth | Inbound request verification, sandbox token minting |
| `SLACK_SIGNING_SECRET` | api | Slack webhook HMAC verification |
| `UI_PASSWORD` | auth | UI login gate |

These are the **only** secrets that exist as environment variables in non-firewall
containers. They are for inbound auth, not outbound API calls.

### Tools and the `secret()` Function

Tools run **in the API process** (not in sandboxes). When a sandbox agent calls
a tool, it makes a REST call to `/tools/{name}/{method}`, and the API executes
the tool's Python code in-process.

The `secret()` function (from `shared.tool_sdk`) resolves secrets as **stub values**:
- `secret("FOO")` returns `"FOO"` (the key name itself)
- The tool puts this in an HTTP header
- The outbound request goes through `HTTPS_PROXY` → firewall
- The firewall replaces `"FOO"` with the real secret value

**`secret()` must never fall back to `os.environ` or `EnvBackend`.** If it did,
any real secret that leaked into the environment would bypass the firewall entirely.

### Tools That Compute Signatures

Some tools (Coinbase, FalconX, Bloomberg, Anchorage) use HMAC signing where the
secret is used to **compute a signature**, not just passed in a header. These
cannot work with stub injection because the firewall can't replicate the signing
logic. These tools require special handling (see individual tool docs).

### What HTTPS_PROXY / NO_PROXY Actually Do

| Env var | Set on | Effect |
|---------|--------|--------|
| `HTTPS_PROXY=http://firewall:8080` | api, sandbox | All outbound HTTPS routes through the firewall for credential injection |
| `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` | api, sandbox | Trust the firewall's mitmproxy CA cert so TLS interception works |
| `NO_PROXY=localhost,127.0.0.1,postgres,...` | api, sandbox | Internal service-to-service HTTP calls bypass the proxy |
| `NODE_EXTRA_CA_CERTS` | slackbot | Trust firewall CA for any outbound HTTPS from Node.js |

**Note on Node.js:** Native `fetch()` (undici) does **not** automatically respect
`HTTPS_PROXY`. The slackbot must either use a `ProxyAgent` dispatcher or be given
an explicit exception for `SLACK_BOT_TOKEN` as a bootstrap secret.

### Kill Switch

Stopping the `secrets` and `firewall` containers immediately terminates all secret
access across the stack. Secrets are cached for only 30 seconds in the firewall.
The system fails closed — sandboxes and tools lose all credential access instantly.

## Directory Structure

```
ai_v2/
├── src/
│   ├── api/              # FastAPI backend (routers/, agent.py, app.py, mcp_server.py)
│   ├── secret_backends/  # Pluggable secret resolution (stub, env, http, composite)
│   ├── secret_manager/   # 1Password vault cache sidecar (:8100)
│   └── shared/           # Shared utilities, tool_manager.py, tool_sdk.py
├── services/
│   ├── auth/             # Starlette password-session auth sidecar (:4000)
│   └── firewall/         # mitmproxy addon — credential injection proxy
├── apps/
│   ├── slackbot/         # Next.js — Slack Bolt event listener (pnpm)
│   └── web/              # Next.js — Thread viewer UI, dashboards (pnpm)
├── sandbox/
│   ├── Dockerfile        # Agent container image (Ubuntu 24.04 + uv + gh + node + amp)
│   ├── entrypoint.sh     # Writes harness configs, signals readiness
│   └── SYSTEM_PROMPT.md  # Baked as ~/AGENTS.md — tells harness to curl the API
├── tools/                # Open-source tools (56 — alchemy, dune, etherscan, etc.)
├── tools-paradigm/       # Paradigm-private tools (24 — slack, bloomberg, coinbase, etc.)
├── pi-plugins/           # TypeScript plugins (handoff, tool-harness, system-prompt)
├── migrations/           # Alembic migration versions
├── monitoring/           # nginx.conf, Grafana dashboards, Prometheus, VictoriaLogs
├── scripts/              # Operational scripts
├── tests/                # pytest tests
├── docker-compose.yml    # Full stack
├── Dockerfile            # API image
└── pyproject.toml        # Python deps (uv)
```

## Tool Conventions

Tools live in `tools/` (open-source) or `tools-paradigm/` (private). Each tool
is a directory with `client.py` and `pyproject.toml`.

### pyproject.toml

```toml
[project]
name = "my-tool"
description = "What this tool does"
dependencies = ["httpx"]

[tool.ai-v2]
module = "client.py"
hosts = ["api.example.com"]        # required — which domains this tool calls
secrets = ["EXAMPLE_API_KEY"]      # required — which secrets it needs
```

### client.py

```python
from shared.tool_sdk import secret

class MyClient:
    def __init__(self):
        self.api_key = secret("EXAMPLE_API_KEY")  # returns stub, not real key

    def get_data(self, query: str) -> dict:
        resp = httpx.get("https://api.example.com/data",
                         headers={"Authorization": f"Bearer {self.api_key}"},
                         params={"q": query})
        return resp.json()

def _client():
    return MyClient()
```

- `client.py`: NO `load_dotenv()`. Secrets via `secret()` only.
- `cli.py` (optional): YES `load_dotenv()`. Thin typer wrapper for local testing.
- Methods starting with `_` are excluded from registration.
- Tools are hot-reloaded on file change — no container restart needed.

## Deployment

All deploys happen via GitHub Actions on merge to `main`. **Never SSH to deploy.**

| Change | Deploy action |
|--------|--------------|
| `tools/**` or `tools-paradigm/**` | Zero-downtime hot-reload (file watcher) |
| `src/**` | `docker compose up -d --build api` |
| `apps/slackbot/**` | `docker compose up -d --build slackbot` |
| `apps/web/**` | `docker compose up -d --build web` |
| `sandbox/**` | `docker build -t agent2:latest sandbox/` |
| `services/firewall/**` | `docker compose up -d --build firewall` |

**⚠️  NEVER manually restart the `secrets` container.** It requires
`OP_SERVICE_ACCOUNT_TOKEN` which is only injected by CI. Manual restart
will start it without the token, breaking all secret resolution.

## Development

```bash
make lint             # ruff check + format --check
make fmt              # auto-fix
make test             # pytest
```

### E2E Testing (without Slack)

```bash
docker compose up -d postgres api
docker build -t agent2:latest sandbox/
source .env

# Execute a message (auto-spawns sandbox container)
curl -s -X POST http://localhost:8000/agent/execute \
  -H "Authorization: Bearer $API_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"slack_thread_key": "test:e2e-1", "message": "hello", "harness": "amp"}'

# Follow-up (same container, same session)
curl -s -X POST http://localhost:8000/agent/execute \
  -H "Authorization: Bearer $API_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"slack_thread_key": "test:e2e-1", "message": "now do X"}'

# Clean up
curl -s -X POST http://localhost:8000/agent/stop \
  -H "Authorization: Bearer $API_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"slack_thread_key": "test:e2e-1"}'
```

## Code Conventions

- Python 3.11+, `uv` for deps, `ruff` for lint/format (line-length=100)
- `apps/slackbot` and `apps/web` use `pnpm`
- Absolute imports only: `from shared.X`, `from api.X` — no relative imports
- `asyncpg` for Postgres, `pgvector` for embeddings
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
