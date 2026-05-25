---
title: Configuration
description: Reference for Centaur environment variables, where they are set, and what they control.
---

# Configuration

Centaur configuration is split across Kubernetes Secrets, Helm values, and a
small set of runtime-injected sandbox variables.

In the Helm chart, fixed service env vars are rendered from
`contrib/chart/templates/workloads.yaml`. Operator-provided overrides usually
come from `api.extraEnv`, `sandbox.extraEnv`, `slackbot.extraEnv`, or the
pre-created infra Secret selected by `secretManager.existingSecretName`.

Tool credentials are different from platform env vars: tools declare them in
their own `pyproject.toml`, and Centaur resolves them through `secret(...)` and
iron-proxy instead of putting raw credentials in the API or sandbox.

## Required service secrets

| Env var | Where set | Controls |
| --- | --- | --- |
| `DATABASE_URL` | `secretManager.existingSecretName`; local `just bootstrap-secrets` creates it in `centaur-infra-env`. | API and Slackbot Postgres connection. Required by the API entrypoint. |
| `SLACK_SIGNING_SECRET` | `secretManager.existingSecretName`; local bootstrap reads it from the shell. | Verifies Slack webhook signatures in the API and Slackbot. Required by the API entrypoint. |
| `SLACKBOT_API_KEY` | `secretManager.existingSecretName`; local bootstrap reads it from the shell. | Static DB-backed service key bootstrapped as `service:slackbot`; Slackbot uses it to call the API. Required by the API entrypoint. |
| `SLACK_BOT_TOKEN` | `secretManager.existingSecretName`; local bootstrap reads it from the shell. | Slack Web API token used by Slackbot and Slack tools. `SLACK_TOKEN` is accepted as an API-container alias. |
| `SANDBOX_SIGNING_KEY` | `secretManager.existingSecretName`; local bootstrap generates it. | HMAC key used by the API to mint `sbx1.*` sandbox tokens. Falls back to `API_SECRET_KEY` only when unset. |
| `IRON_MANAGEMENT_API_KEY` | `secretManager.existingSecretName`; local bootstrap generates it. | Management API key mounted into per-sandbox iron-proxy containers. |
| `OP_SERVICE_ACCOUNT_TOKEN` | Local bootstrap shell env, then `centaur-infra-env`; production Secret if using 1Password service-account resolution. | Lets iron-proxy resolve `op://...` references when `FIREWALL_MANAGER_SECRET_SOURCE=onepassword`. |
| `OP_VAULT` | Local bootstrap shell env, then `centaur-infra-env`; chart default is `ai-agents` if omitted. | 1Password vault name or id used when rendering `op://<vault>/<secret>/credential` references. |
| `OP_CONNECT_TOKEN` | Optional local bootstrap shell env, then `centaur-infra-env`. | Token mounted into iron-proxy when using the `onepassword-connect` secret source. |
| `OP_CONNECT_CREDENTIALS_FILE` | Local shell before `just up` or `just deploy`. | When set, `just deploy` enables the 1Password Connect subchart and bootstrap creates the Connect credentials Secret. |
| `LOCAL_DEV_API_KEY` | Optional API env or test fixture. | Static DB-backed admin/dev API key bootstrapped as `service:local-dev`. |

## API service

| Env var | Where set | Controls |
| --- | --- | --- |
| `CENTAUR_DEFAULT_HARNESS` | Helm `api.defaultHarness`. | Default harness when a request does not specify one. |
| `CENTAUR_ENVIRONMENT` | `api.extraEnv`, `slackbot.extraEnv`, or deployment env. | Environment label attached to traces and telemetry. |
| `CENTAUR_LOG_LEVEL` | Helm hardcodes `info`; override with `api.extraEnv`. | API structured log level. |
| `CENTAUR_SERVICE_NAME` | `api.extraEnv`. | Default `service` field in API logs. Defaults to `api`. |
| `LOG_LEVEL` | Process env fallback. | Fallback log level when `CENTAUR_LOG_LEVEL` is unset. |
| `SHUTDOWN_DRAIN_TIMEOUT_S` | `api.extraEnv`. | Graceful shutdown wait for in-flight HTTP requests. Defaults to `25`. |
| `EXECUTION_WORKER_ENABLED` | Helm `api.executionWorkerEnabled`. | Starts the durable agent execution worker loop. |
| `WORKFLOW_WORKER_ENABLED` | Helm `api.workflowWorkerEnabled`. | Starts the durable workflow worker loop. |
| `WARM_POOL_ENABLED` | Helm `api.warmPoolEnabled`. | Starts warm sandbox replenishment. |
| `PLUGIN_WATCHER_ENABLED` | Helm `api.pluginWatcherEnabled`. | Enables local file watchers for tool and workflow hot reload. |
| `TOOL_DIRS` | Helm renders `/app/tools` plus overlay tools when overlay is mounted. | Colon-separated tool plugin directories. |
| `PLUGINS_DIR` | API process fallback only. | Fallback tool directory when `TOOL_DIRS` and `tools.toml` are absent. |
| `WORKFLOW_DIRS` | Helm renders `/app/workflows` plus overlay workflows when overlay is mounted. | Colon-separated workflow plugin directories. |
| `CENTAUR_OVERLAY_DIR` | Helm `overlay.mountPath`. | Mounted overlay root used for tools, workflows, migrations, prompts, and skills. |
| `CENTAUR_OVERLAY_IMAGE` | Helm `overlay.image.repository` + `overlay.image.tag`. | Overlay image copied into sandbox pods. |
| `CENTAUR_OVERLAY_IMAGE_PULL_POLICY` | Helm `overlay.image.pullPolicy`. | Pull policy for overlay init containers. |
| `CENTAUR_OVERLAY_IMAGE_SOURCE_PATH` | Helm `overlay.image.sourcePath`. | Source path inside the overlay image. Defaults to `/overlay`. |
| `CENTAUR_ENABLE_GCLOUD_BOOTSTRAP` | `api.extraEnv`. | Enables API-entrypoint setup of gcloud ADC from `GCP_GCLOUD_CREDENTIAL`. |
| `GCP_GCLOUD_CREDENTIAL` | Secret or `api.extraEnv` when gcloud bootstrap is enabled. | JSON credential written into the API container's gcloud config. |
| `GCLOUD_PROJECT` | Optional `api.extraEnv`. | Overrides project selected during gcloud bootstrap. |
| `GITHUB_TOKEN` | Canonical API env or tool secret. | GitHub token available to code that runs in the API process; aliases are `GH_TOKEN` and `GITHUB_PAT`. |
| `GH_TOKEN` | API env alias. | Used by the API entrypoint to populate `GITHUB_TOKEN` when `GITHUB_TOKEN` is empty. |
| `GITHUB_PAT` | API env alias. | Used by the API entrypoint to populate `GITHUB_TOKEN` when `GITHUB_TOKEN` is empty. |
| `ANTHROPIC_API_KEY` | API env or tool secret. | Canonical Anthropic key name for libraries and proxy placeholder flows. Aliases are `ANTHROPIC_KEY` and `CLAUDE_API_KEY`. |
| `ANTHROPIC_KEY` | API env alias. | Populates `ANTHROPIC_API_KEY` when empty. |
| `CLAUDE_API_KEY` | API env alias. | Populates `ANTHROPIC_API_KEY` when empty. |
| `CLAUDE_MODEL` | `api.extraEnv` or request model override. | Maps Claude shorthand models for execution requests. |
| `CODEX_MODEL` | `api.extraEnv` or request model override. | Maps Codex model selection for execution requests. |
| `SLACKBOT_URL` | Helm renders the in-cluster Slackbot URL. | API callback URL for Slack final delivery and live delivery recovery. |
| `FINAL_DELIVERY_MAX_ATTEMPTS` | `api.extraEnv`. | Max final-delivery retry attempts. Defaults to `50`. |
| `FINAL_DELIVERY_READY_GRACE_S` | `api.extraEnv`. | Grace period before claiming final-delivery work. Defaults to `10`. |

## Execution control

| Env var | Where set | Controls |
| --- | --- | --- |
| `EXECUTION_WORKER_CONCURRENCY` | `api.extraEnv`. | Max concurrently claimed execution requests. Defaults to `128`. |
| `EXECUTION_RESERVED_USER_SLOTS` | `api.extraEnv`. | Worker slots reserved for non-workflow user requests. Defaults to `16`. |
| `EXECUTION_WORKER_LEASE_S` | `api.extraEnv`. | Execution worker lease duration. Defaults to `60`. |
| `EXECUTION_SILENCE_TIMEOUT_S` | `api.extraEnv`. | Watchdog timeout when no harness output is seen. Defaults to `600`. |
| `EXECUTION_TOOL_SILENCE_TIMEOUT_S` | `api.extraEnv`. | Longer watchdog timeout while tools are active. Defaults to `1800`. |
| `EXECUTION_HARD_TIMEOUT_S` | `api.extraEnv`. | Absolute execution timeout. Defaults to `3600`. |
| `EXECUTION_WATCHDOG_POLL_S` | `api.extraEnv`. | Watchdog polling interval. Defaults to `1`. |
| `EXECUTION_RECONCILE_INTERVAL_S` | `api.extraEnv`. | Execution reconciliation loop interval. Defaults to `0.5`. |
| `EXECUTION_RECONCILE_STARTUP_LIMIT` | `api.extraEnv`. | Max interrupted executions recovered at startup. Defaults to `500`. |
| `EXECUTION_STALE_RECOVERY_INTERVAL_S` | `api.extraEnv`. | Minimum interval between stale-running recovery passes. Defaults to `5`. |
| `EXECUTION_STREAM_EOF_RETRY_DELAY_S` | `api.extraEnv`. | Delay before retrying after sandbox stream EOF. Defaults to `1`. |
| `THREAD_FAILURE_LOOP_WINDOW_S` | `api.extraEnv`. | Window for detecting repeated thread failures. Defaults to `300`. |
| `THREAD_FAILURE_LOOP_THRESHOLD` | `api.extraEnv`. | Failure count threshold inside the loop window. Defaults to `3`. |
| `IDLE_TTL_S` | `api.extraEnv`. | Idle sandbox retention before cleanup. Defaults to `86400`. |
| `SUSPENDED_RETENTION_S` | `api.extraEnv`. | Suspended sandbox retention. Defaults to 7 days. |
| `MAX_ACTIVE_SANDBOX_SESSIONS` | `api.extraEnv`. | Max active sandbox sessions tracked by agent cleanup. Defaults to `45`. |
| `STREAM_EOF_REATTACH_MAX` | `api.extraEnv`. | Max reattach attempts after stream EOF. Defaults to `6`. |
| `STREAM_EOF_REATTACH_BACKOFF_S` | `api.extraEnv`. | Delay between stream EOF reattach attempts. Defaults to `1`. |

## Workflow engine

| Env var | Where set | Controls |
| --- | --- | --- |
| `WORKFLOW_WORKER_CONCURRENCY` | `api.extraEnv`. | Number of workflow worker tasks. Defaults to `2`. |
| `WORKFLOW_WORKER_LEASE_S` | `api.extraEnv`. | Workflow run lease duration. Defaults to `30`. |
| `WORKFLOW_RECONCILE_INTERVAL_S` | `api.extraEnv`. | Workflow reconciliation polling interval. Defaults to `0.5`. |
| `WORKFLOW_SCHEDULE_TICK_INTERVAL_S` | `api.extraEnv`. | Schedule tick interval. Defaults to `5`. |
| `WORKFLOW_SCHEDULE_CATCHUP_LIMIT` | `api.extraEnv`. | Max missed schedule runs created per tick. Defaults to `5`. |
| `WORKFLOW_SCHEDULE_MISFIRE_GRACE_S` | `api.extraEnv`. | Grace period for late scheduled runs. Defaults to `90`. |
| `WORKFLOW_RESUSPEND_BACKOFF_S` | `api.extraEnv`. | Minimum delay before re-claiming a still-waiting workflow. Defaults to `5`. |
| `MY_THREAD_KEY` | Workflow-specific env. | Optional fallback thread key for generic workflow agent steps. |
| `<WORKFLOW_NAME>_THREAD_KEY` | Workflow-specific env. | Per-workflow fallback thread key. |
| `<WORKFLOW_NAME>_SLACK_CHANNEL` | Workflow-specific env. | Per-workflow fallback Slack channel. |
| `<WEBHOOK_SECRET_REF>` | API env or Secret chosen by the webhook spec. | HMAC secret for workflow webhooks, for example `GITHUB_WEBHOOK_SECRET`. |

## Slack ETL workflows

| Env var | Where set | Controls |
| --- | --- | --- |
| `SLACK_ETL_ENABLED` | Helm `api.slackEtlEnabled`. | Master switch for Slack sync, backfill, and company-context schedules. |
| `SLACK_SYNC_INTERVAL_SECONDS` | Helm `api.slackSyncIntervalSeconds`. | Incremental Slack sync schedule interval. Defaults to `3600`. |
| `SLACK_SYNC_BACKFILL_LOOKBACK_DAYS` | Helm `api.slackSyncBackfillLookbackDays`. | Channel history lookback for Slack sync bootstrap jobs. Defaults to `30`. |
| `SLACK_SYNC_THREAD_LOOKBACK_DAYS` | Helm `api.slackSyncThreadLookbackDays`. | Thread refresh lookback. Defaults to `3`. |
| `SLACK_ETL_EXCLUDED_CHANNEL_PATTERNS` | Helm `api.slackEtlExcludedChannelPatterns`. | Comma-separated channel-name globs excluded from Slack ETL. |
| `SLACK_BACKFILL_ENABLED` | `api.extraEnv`. | Enables the Slack backfill worker when `SLACK_ETL_ENABLED` is true. Defaults to true. |
| `SLACK_BACKFILL_INTERVAL_SECONDS` | Helm `api.slackBackfillIntervalSeconds`. | Slack backfill schedule interval. Defaults to `60` in workflow code, `3600` in chart values. |
| `SLACK_BACKFILL_CHANNEL_BATCH_LIMIT` | Helm `api.slackBackfillChannelBatchLimit`. | Backfill jobs claimed per run. Defaults to `50` in workflow code, `20` in chart values. |
| `SLACK_BACKFILL_CHANNEL_PAGES_PER_JOB` | `api.extraEnv`. | Max channel-history pages drained per backfill job. Defaults to `5`. |
| `COMPANY_CONTEXT_DOCUMENTS_ENABLED` | `api.extraEnv`. | Enables company-context projection when `SLACK_ETL_ENABLED` is true. Defaults to true. |
| `COMPANY_CONTEXT_DOCUMENTS_INTERVAL_SECONDS` | Helm `api.companyContextDocumentsIntervalSeconds`. | Company-context document projection schedule interval. Defaults to `14400`. |

## Sandbox and Kubernetes backend

| Env var | Where set | Controls |
| --- | --- | --- |
| `AGENT_IMAGE` | Helm `sandbox.image.repository` + `sandbox.image.tag`. | Sandbox image created by the Kubernetes backend. |
| `AGENT_API_URL` | Helm renders the in-cluster API URL. | API URL injected into sandboxes as `CENTAUR_API_URL`; required by the Kubernetes backend. |
| `KUBERNETES_NAMESPACE` | Helm release namespace. | Namespace for sandbox, proxy, Secret, and ConfigMap operations. Falls back to `POD_NAMESPACE` or service-account namespace. |
| `POD_NAMESPACE` | Kubernetes downward API or process env. | Namespace fallback when `KUBERNETES_NAMESPACE` is unset. |
| `KUBERNETES_KUBECONFIG` | `api.extraEnv`, local development only. | Kubeconfig path for out-of-cluster backend clients. |
| `KUBERNETES_AGENT_IMAGE_PULL_POLICY` | Helm `sandbox.image.pullPolicy`. | Sandbox image pull policy. Defaults to `IfNotPresent` in code. |
| `KUBERNETES_SANDBOX_RUNTIME_CLASS_NAME` | Helm `sandbox.runtimeClassName`. | RuntimeClass assigned to sandbox pods. |
| `KUBERNETES_SANDBOX_SERVICE_ACCOUNT_NAME` | `api.extraEnv`. | Optional service account assigned to sandbox pods. |
| `KUBERNETES_SANDBOX_READY_TIMEOUT_S` | `api.extraEnv`. | Sandbox readiness timeout. Defaults to `60`. |
| `KUBERNETES_ATTACH_LOG_TAIL_LINES` | `api.extraEnv`. | Log lines included when attach fails. Defaults to `200`. |
| `KUBERNETES_SANDBOX_CPU_LIMIT` | Helm `sandbox.resources.limits.cpu` or `api.extraEnv`. | CPU limit for sandbox pods. Defaults to `2` when unset. Empty string omits the limit. |
| `KUBERNETES_SANDBOX_MEMORY_LIMIT` | Helm `sandbox.resources.limits.memory` or `api.extraEnv`. | Memory limit for sandbox pods. Defaults to `4Gi` when unset. Empty string omits the limit. |
| `KUBERNETES_SANDBOX_CPU_REQUEST` | Helm `sandbox.resources.requests.cpu`. | CPU request for sandbox pods. |
| `KUBERNETES_SANDBOX_MEMORY_REQUEST` | Helm `sandbox.resources.requests.memory`. | Memory request for sandbox pods. |
| `KUBERNETES_SANDBOX_EXTRA_ENV` | Helm `sandbox.extraEnv`. | JSON list of additional env vars copied into sandbox pods. |
| `KUBERNETES_SANDBOX_IMAGE_PULL_SECRETS` | Helm `global.imagePullSecrets`. | Comma-separated image pull Secret names attached to sandbox pods. |
| `KUBERNETES_FIREWALL_CA_SECRET_NAME` | Helm `firewall.existingCaSecretName` or generated CA Secret. | Secret containing the CA bundle mounted into sandbox/proxy pods. |
| `KUBERNETES_FIREWALL_CA_KEY_SECRET_NAME` | Helm `firewall.existingCaKeySecretName` or generated CA key Secret. | Secret containing the CA key used by per-sandbox iron-proxy. |
| `KUBERNETES_SECRET_ENV_NAME` | Helm `secretManager.existingSecretName`. | Secret read by API-managed per-sandbox iron-proxy pods. |
| `KUBERNETES_SECRET_ENV_PREFIX` | Helm `secretManager.envPrefix`. | Prefix applied when looking up keys inside the Secret. |
| `KUBERNETES_BOOTSTRAP_SECRET_NAME` | Helm `secrets.bootstrapSecretName`. | Optional Secret used for sandbox bootstrap material. |
| `KUBERNETES_IRON_PROXY_IMAGE` | Helm `ironProxy.image.repository` + `ironProxy.image.tag`. | Per-sandbox iron-proxy image. |
| `KUBERNETES_IRON_PROXY_IMAGE_PULL_POLICY` | Helm `ironProxy.image.pullPolicy`. | Per-sandbox iron-proxy pull policy. |
| `KUBERNETES_IRON_PROXY_PORT` | Helm `ironProxy.service.proxyPort`. | Proxy listener port. Defaults to `8080`. |
| `KUBERNETES_IRON_PROXY_MANAGEMENT_PORT` | Helm `ironProxy.service.managementPort`. | Proxy management port. Defaults to `9092`. |
| `KUBERNETES_IRON_PROXY_HEALTH_PORT` | Helm `ironProxy.service.healthPort`. | Proxy health port. Defaults to `9090`. |
| `FIREWALL_MANAGER_SECRET_SOURCE` | Helm `ironProxy.secretSource`. | Secret-source renderer for API-owned iron-proxy config: `env`, `onepassword`, or `onepassword-connect`. |
| `FIREWALL_MANAGER_SECRET_TTL` | Helm `ironProxy.secretTtl`. | Cache TTL for rendered secret references. Defaults to `10m`. |
| `KUBERNETES_FIREWALL_MANAGER_SECRET_SOURCE` | Helm `ironProxy.secretSource`. | Secret source used when creating per-sandbox proxy pods. |
| `KUBERNETES_OP_CONNECT_HOST` | Helm OnePassword Connect service URL. | Connect host injected into per-sandbox proxy pods when using `onepassword-connect`. |
| `KUBERNETES_OP_CONNECT_APP_NAME` | `api.extraEnv`. | OnePassword Connect app/service name fallback. Defaults to `onepassword-connect`. |
| `KUBERNETES_OP_CONNECT_PORT` | `api.extraEnv`. | OnePassword Connect port fallback. Defaults to `8080`. |
| `KUBERNETES_API_POD_LABEL_SELECTOR` | Helm renders API labels. | Selector used by API-managed proxy policies to identify API pods. |
| `KUBERNETES_EGRESS_DISCOVERY_ENABLED` | Helm `api.egressDiscovery.enabled`. | Enables discovery of egress services for NetworkPolicies. |
| `KUBERNETES_EGRESS_SERVICE_NAMESPACE` | Helm `api.egressDiscovery.namespace`. | Namespace scanned for egress services. |
| `KUBERNETES_CLUSTER_DOMAIN` | Helm `api.egressDiscovery.clusterDomain`. | Cluster DNS suffix for service hostnames. |
| `KUBERNETES_EGRESS_TAILNET_FQDN_ANNOTATION` | Helm `api.egressDiscovery.tailnetFqdnAnnotation`. | Annotation key for Tailscale tailnet FQDN discovery. |
| `REPOS_PATH` | Helm `sandbox.reposPath`. | Host/repo cache path mounted into sandboxes. |

## Sandbox runtime injection

These values are set by the API when it creates or claims a sandbox pod.
Operators usually should not set them by hand.

| Env var | Where set | Controls |
| --- | --- | --- |
| `CENTAUR_API_URL` | API sandbox creation from `AGENT_API_URL`. | In-cluster API URL used by `call` and the SDK. |
| `CENTAUR_API_KEY` | API sandbox creation. | Short-lived `sbx1.*` token scoped to the thread and tools. |
| `CENTAUR_THREAD_KEY` | API sandbox creation. | Thread identity used by tools, tracing, and scope checks. |
| `CENTAUR_TRACE_ID` | API sandbox creation. | Stable trace id propagated to harnesses, tools, and Laminar. |
| `AMP_MODE` | API sandbox creation from API env. | Amp wrapper mode. Defaults to `deep`. |
| `AMP_THREAD_VISIBILITY` | API sandbox creation from API env. | Optional Amp thread visibility setting. |
| `AMP_CONTINUE_THREAD_ID` | API sandbox resume path. | Harness thread/session id to resume. |
| `ANTHROPIC_API_KEY` | API sandbox creation as a placeholder. | Stub value for harness initialization; iron-proxy injects the real credential on outbound requests. |
| `OPENAI_API_KEY` | API sandbox creation as a placeholder. | Stub value for OpenAI/Codex initialization; real credential is injected by iron-proxy. |
| `AMP_API_KEY` | API sandbox creation as a placeholder. | Stub value for Amp initialization; real credential is injected by iron-proxy. |
| `GITHUB_TOKEN` | API sandbox creation as a placeholder or entrypoint auth token. | Stub or real token used by GitHub CLI/git setup, depending on deployment. |
| `FIREWALL_HOST` | API sandbox creation. | Per-sandbox proxy host used by wrappers and entrypoint. |
| `HTTPS_PROXY`, `HTTP_PROXY`, `https_proxy`, `http_proxy` | API sandbox creation. | Routes sandbox outbound traffic through iron-proxy. |
| `NO_PROXY`, `no_proxy` | API sandbox creation. | Bypasses proxy for localhost, API, and the proxy itself. |
| `NODE_EXTRA_CA_CERTS` | API sandbox creation. | CA bundle for Node-based harnesses. |
| `REQUESTS_CA_BUNDLE` | API sandbox creation. | CA bundle for Python requests/httpx clients. |
| `SSL_CERT_FILE` | API sandbox creation. | CA bundle for OpenSSL-based clients. |
| `GIT_SSL_CAINFO` | API sandbox creation. | CA bundle for git. |
| `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY` | API sandbox creation. | Claude Code hardening flag. |
| `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL` | API sandbox creation. | Claude Code hardening flag. |
| `CLAUDE_CODE_PROXY_RESOLVES_HOSTS` | API sandbox creation. | Forces Claude Code proxy host resolution. |
| `CLAUDE_CODE_CERT_STORE` | API sandbox creation. | Claude Code certificate store selection. |
| `DISABLE_ERROR_REPORTING` | API sandbox creation. | Disables harness error reporting. |
| `DISABLE_FEEDBACK_COMMAND` | API sandbox creation. | Disables feedback commands in harnesses. |
| `DISABLE_GROWTHBOOK` | API sandbox creation. | Disables GrowthBook in harnesses. |
| `DISABLE_UPDATES` | API sandbox creation. | Disables update checks in harnesses. |
| `PG_PROXY_PASSWORD_<SECRET_NAME>` | API per-sandbox proxy creation. | Per-listener password for `pg_dsn` tool secrets. |
| `<PG_DSN_SECRET_NAME>` | API sandbox creation. | Local proxied Postgres DSN exposed to tools that declare `pg_dsn` secrets. |

## Sandbox entrypoint and wrappers

| Env var | Where set | Controls |
| --- | --- | --- |
| `CENTAUR_HARNESS_CONFIG_DIR` | Sandbox image or `sandbox.extraEnv`. | Directory containing harness config templates. Defaults to `~/harness`. |
| `CENTAUR_HARNESS_ADAPTER` | Sandbox image or `sandbox.extraEnv`. | Optional adapter executable run before the harness starts. |
| `AGENT_REPO` | API runtime assignment metadata or `sandbox.extraEnv`. | Repository cloned into the sandbox workspace from `~/github/<repo>`. |
| `AGENT_PERSONA` | API runtime assignment metadata. | Persona prompt selected for the sandbox. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Sandbox entrypoint or `sandbox.extraEnv`. | ADC file path; entrypoint creates a local stub when unset. |
| `CODEX_API_KEY` | `sandbox.extraEnv` or proxy-injected secret flow. | If present, used by the entrypoint for `codex login`; otherwise it falls back to `OPENAI_API_KEY`. |
| `CODEX_HOME` | `sandbox.extraEnv`. | Codex config home. Defaults to `~/.codex`. |
| `CODEX_CONTINUE_THREAD_ID` | Runtime resume env. | Codex wrapper resume thread id. Falls back to `AMP_CONTINUE_THREAD_ID`. |
| `CLAUDE_CONTINUE_SESSION_ID` | Runtime resume env. | Claude wrapper resume session id. Falls back to `AMP_CONTINUE_THREAD_ID`. |
| `CLAUDE_MODEL` | API env or `sandbox.extraEnv`. | Claude wrapper model shorthand. Defaults to `opus`. |
| `CODEX_OTEL_LAMINAR_ENDPOINT` | API env passed through to sandbox. | Direct OTLP traces endpoint for Codex. |
| `CODEX_OTEL_LAMINAR_BASE_URL` | API env passed through to sandbox. | Base URL used to derive Codex OTLP traces endpoint. |
| `CODEX_OTEL_ENVIRONMENT` | API env passed through to sandbox. | Environment label for Codex telemetry. |
| `CLAUDE_OTEL_LAMINAR_ENDPOINT` | `sandbox.extraEnv`. | Direct OTLP traces endpoint for Claude Code. |
| `CLAUDE_OTEL_LAMINAR_BASE_URL` | `sandbox.extraEnv`. | Base URL used to derive Claude OTLP traces endpoint. |
| `CLAUDE_OTEL_ENVIRONMENT` | `sandbox.extraEnv`. | Environment label for Claude telemetry. |
| `LMNR_PROJECT_API_KEY` | Secret/Helm optional; passed through to sandbox. | Laminar project key for API, Slackbot, Codex, and Claude tracing. |
| `LMNR_BASE_URL` | Secret/Helm optional; passed through to sandbox. | Laminar API base URL. |
| `LMNR_HTTP_PORT` | Helm Laminar values. | Laminar HTTP port for API and Slackbot SDK initialization. |
| `LMNR_GRPC_PORT` | Helm Laminar values. | Laminar gRPC port for API and Slackbot SDK initialization. |
| `DEPLOY_ENV` | Deployment env or `sandbox.extraEnv`. | Fallback telemetry environment label. |
| `ENVIRONMENT` | Deployment env or `sandbox.extraEnv`. | Fallback telemetry environment label. |
| `TRACEPARENT` | Codex wrapper. | W3C trace context emitted for downstream tools. |
| `CALL_TIMEOUT_SECONDS` | Set inside a sandbox before calling `call`. | Curl watchdog for API tool calls. Defaults to `1800`. |
| `SLACK_CHANNEL` | Sandbox env for `slack-upload.sh`. | Slack channel target for file uploads. |
| `SLACK_THREAD_TS` | Sandbox env for `slack-upload.sh`. | Slack thread target for file uploads. |

## Slackbot service

| Env var | Where set | Controls |
| --- | --- | --- |
| `NODE_ENV` | Runtime environment. | Development mode enables route listing; also labels Slackbot telemetry. Defaults to `development`. |
| `PORT` | Container env or platform. | Slackbot HTTP listen port. Defaults to `3001`. |
| `SLACK_API_URL` | `slackbot.extraEnv`. | Optional Slack Web API base URL override. |
| `CENTAUR_API_URL` | Helm renders in-cluster API URL. | Slackbot API base URL. Defaults to `http://localhost:8000` outside Helm. |
| `CENTAUR_API_KEY` | Optional Secret/env. | Fallback API key when `SLACKBOT_API_KEY` is unset. |
| `CENTAUR_SLACK_EVENTS_PATH` | `slackbot.extraEnv`. | Slack Events API route. Defaults to `/api/webhooks/slack`. |
| `RUNTIME_ERROR_ALERT_CHANNEL` | Helm `slackbot.runtimeErrorAlertChannel`. | Slack channel for runtime error alerts. |
| `SLACK_EVENT_DEDUP_TTL_MS` | `slackbot.extraEnv`. | Slack event deduplication TTL. Defaults to 10 minutes. |
| `SLACK_SIGNATURE_MAX_AGE_SECONDS` | `slackbot.extraEnv`. | Max accepted Slack request signature age. Defaults to 300 seconds. |
| `LINEAR_API_KEY` | `slackbot.extraEnv` or Secret. | Enables Slack feedback slash commands to create Linear issues. |
| `SLACK_FEEDBACK_COMMANDS` | `slackbot.extraEnv`. | Space/comma-separated feedback slash commands. Defaults to `/website-feedback`. |
| `SLACK_FEEDBACK_LINEAR_TEAM_ID` | `slackbot.extraEnv`. | Linear team id for feedback issues. |
| `SLACK_FEEDBACK_LINEAR_PROJECT_ID` | `slackbot.extraEnv`. | Linear project id for feedback issues. |
| `SLACK_FEEDBACK_ALLOWED_CHANNELS` | `slackbot.extraEnv`. | Optional space/comma-separated allowlist of Slack channel ids for feedback commands. |
| `SLACKBOT_EXTERNAL_ORG_ALLOWLIST` | `slackbot.extraEnv`. | Space/comma-separated Slack team ids allowed for external org handoff. |
| `COMMIT_SHA` | Image build or deployment env. | Commit reported by Slackbot health metadata. Defaults to `local`. |

## Observability and metrics

| Env var | Where set | Controls |
| --- | --- | --- |
| `VICTORIAMETRICS_URL` | `api.extraEnv`. | VictoriaMetrics remote write/import endpoint base. Defaults to `http://victoriametrics:8428`. |
| `VICTORIAMETRICS_PUSH_ENABLED` | Helm `api.victoriaMetricsPushEnabled`. | Enables API metrics push loop. Defaults to enabled in code, disabled in chart values. |
| `LMNR_PROJECT_API_KEY` | Secret selected by chart or optional local bootstrap. | Enables Laminar tracing for API and Slackbot; also passed into sandboxes when set. |
| `LMNR_BASE_URL` | Secret selected by chart, local bootstrap, or Laminar chart helper. | Laminar base URL. Defaults to public Laminar in API code when only the key is set. |
| `LMNR_HTTP_PORT` | Helm Laminar values. | Optional Laminar app-server HTTP port. |
| `LMNR_GRPC_PORT` | Helm Laminar values. | Optional Laminar app-server gRPC port. |

## Retention

| Env var | Where set | Controls |
| --- | --- | --- |
| `CENTAUR_RETENTION_ATTACHMENTS_TTL_DAYS` | `api.extraEnv`. | Deletes attachment rows older than this many days. Empty, `0`, `off`, or `infinite` disables attachment retention. |
| `CENTAUR_RETENTION_TRANSCRIPTS_TTL_DAYS` | `api.extraEnv`. | Deletes transcript rows older than this many days. Empty, `0`, `off`, or `infinite` disables transcript retention. |
| `CENTAUR_RETENTION_SWEEP_INTERVAL_SECONDS` | `api.extraEnv`. | Retention sweep interval. Defaults to `3600`. |
| `CENTAUR_RETENTION_BATCH_SIZE` | `api.extraEnv`. | Max rows processed per retention target per sweep. Defaults to `500`. |
| `CENTAUR_RETENTION_DRY_RUN` | `api.extraEnv`. | Logs retention counts without deleting rows. Defaults to false. |

## Tool execution

| Env var | Where set | Controls |
| --- | --- | --- |
| `TOOL_CALL_TIMEOUT_S` | `api.extraEnv`. | Default wall-clock timeout for one tool call. Defaults to `120`. |
| `TOOL_BINARY_INLINE_MAX_BYTES` | `api.extraEnv`. | Max inline binary payload size before extraction. Defaults to 1 MiB, minimum 1 KiB. |
| `TOOL_BINARY_PREVIEW_BYTES` | `api.extraEnv`. | Binary preview bytes kept in tool results. Defaults to 32 KiB, minimum 128 B. |
| `<TOOL_TIMEOUT_ENV>` | Tool config `timeout_env`. | Optional per-tool timeout override named by the tool config. |

## Local development and scripts

| Env var | Where set | Controls |
| --- | --- | --- |
| `CENTAUR_NAMESPACE` | Local shell or `.env`. | Namespace used by `just`, dbmate wrapper, and Slack debug scripts. Defaults to `centaur`. |
| `CENTAUR_RELEASE` | Local shell or `.env`. | Helm release used by `just` and Slack debug scripts. Defaults to `centaur`. |
| `JUST_BUILD_SEQUENTIAL` | Local shell. | Runs service Docker builds sequentially instead of in parallel. |
| `CENTAUR_MIGRATIONS_DEPLOYMENT` | Local shell. | API deployment name used by `contrib/scripts/dbmate`. Defaults to `centaur-centaur-api`. |
| `CENTAUR_MIGRATIONS_HOST_DIR` | Local shell. | Core migrations directory on the host. |
| `CENTAUR_MIGRATIONS_CONTAINER_DIR` | Local shell. | Core migrations directory in the API container. |
| `CENTAUR_OVERLAY_HOST_DIR` | Local shell. | Overlay checkout root used by the dbmate wrapper. |
| `CENTAUR_OVERLAY_DIR` | Local shell or chart. | Overlay path in the API container for migrations. |
| `CENTAUR_API_URL` | Local shell for contrib scripts. | API URL used by scripts such as `muesli-push.sh`. |
| `CENTAUR_API_KEY` | Local shell for contrib scripts. | API key used by scripts such as `muesli-push.sh`. |
| `MUESLI_CLI` | Local shell. | Path to `muesli-cli` for the Muesli push helper. |
| `MUESLI_HOST` | Local shell. | Host label stored with Muesli meeting ingestion. |
| `MUESLI_PUSH_LOG` | Local shell. | Log path for the Muesli push helper. |
| `MUESLI_SLACK_CHANNEL` | Local shell. | Optional Slack channel passed to the Muesli workflow. |

## Tool secrets

These are not global platform knobs. Each name is declared by one or more tool
plugins under `tools/**/pyproject.toml`; the API renders them into iron-proxy
configuration, and sandbox code receives either a safe placeholder or a proxied
DSN.

| Secret env var | Declared by | Controls |
| --- | --- | --- |
| `AIRTABLE_API_KEY` | `tools/productivity/airtable` | Airtable API access. |
| `ALCHEMY_API_KEY` | `tools/crypto/alchemy` | Alchemy API access. |
| `ALLIUM_API_KEY` | `tools/crypto/allium` | Allium API access. |
| `ANTHROPIC_API_KEY` | `tools/research/websearch` | Anthropic model calls used by deep research. |
| `ARKHAM_API_KEY` | `tools/crypto/arkham` | Arkham API access. |
| `ASHBY_API_KEY` | `tools/business/ashby` | Ashby API access. |
| `ATTIO_API_KEY` | `tools/business/attio` | Attio API access. |
| `BROWSER_USE_API_KEY` | `tools/research/archiver`, `tools/research/docsend` | Browser-use cloud sessions. |
| `COINGECKO_API_KEY` | `tools/crypto/coingecko` | CoinGecko API access. |
| `COINMETRICS_API_KEY` | `tools/crypto/coinmetrics` | Coin Metrics API access. |
| `COMPOSIO_API_KEY` | `tools/productivity/composio` | Composio external service tools. |
| `CRUNCHBASE_API_KEY` | `tools/research/crunchbase` | Crunchbase API access. |
| `DATABENTO_API_KEY` | `tools/crypto/databento` | Databento API access. |
| `DATAGOV_API_KEY` | `tools/research/congress`, `tools/research/openfec` | Data.gov API-backed research tools. |
| `DEBANK_API_KEY` | `tools/crypto/debank` | DeBank API access. |
| `DEFILLAMA_API_KEY` | `tools/crypto/defillama` | DefiLlama API access. |
| `DUNE_API_KEY` | `tools/crypto/dune` | Dune API access. |
| `EODHD_API_KEY` | `tools/crypto/eodhd` | EODHD market data API access. |
| `ETHERSCAN_API_KEY` | `tools/crypto/etherscan` | Etherscan API access. |
| `EXA_API_KEY` | `tools/research/websearch` | Exa search API access. |
| `FIGMA_ACCESS_TOKEN` | `tools/productivity/figma` | Figma API access. |
| `GOOGLE_API_KEY` | `tools/media/veo3`, `tools/media/nano-banana`, `tools/research/youtube` | Google media and YouTube API access. |
| `GOOGLE_TOKEN_JSON` | `tools/productivity/gsuite` | Google Workspace OAuth token JSON. |
| `GRAFANA_API_KEY` | `tools/infra/grafana` | Grafana API access. |
| `GRAFANA_URL` | `tools/infra/grafana` | Grafana base URL. |
| `GRANOLA_API_KEY` | `tools/productivity/granola` | Granola API access. |
| `HARMONIC_API_KEY` | `tools/research/harmonic` | Harmonic API access. |
| `LEGISTORM_API_KEY` | `tools/research/legistorm` | LegiStorm API access. |
| `LINEAR_API_KEY` | `tools/productivity/linear`; Slackbot feedback integration also reads it. | Linear API access. |
| `LISTENNOTES_KEY` | `tools/research/listennotes` | Listen Notes API access. |
| `MESSARI_API_KEY` | `tools/crypto/messari` | Messari API access. |
| `NANSEN_API_KEY` | `tools/crypto/nansen` | Nansen API access. |
| `NEWSAPI_KEY` | `tools/research/newsapi` | NewsAPI access. |
| `NOTION_API_KEY` | `tools/productivity/notion` | Notion API access. |
| `PLURAL_API_KEY` | `tools/research/plural` | Plural API access. |
| `POSTHOG_API_KEY` | `tools/infra/posthog` | PostHog API access. |
| `POSTHOG_PROJECT_ID` | `tools/infra/posthog` | PostHog project id. |
| `PYLON_API_KEY` | `tools/business/pylon` | Pylon API access. |
| `REDUCTO_API_KEY` | `tools/research/archiver` | Reducto document extraction API access. |
| `SENSOR_TOWER_AUTH_TOKEN` | `tools/research/sensortower` | Sensor Tower API access. |
| `SIMILARWEB_API_KEY` | `tools/research/similarweb` | Similarweb API access. |
| `SLACK_BOT_TOKEN` | `tools/productivity/slack`; Slackbot also reads it. | Slack Web API access. |
| `SNAPSHOT_API_KEY` | `tools/crypto/snapshot` | Snapshot API access. |
| `STANDARD_METRICS_CLIENT_ID` | `tools/crypto/standard-metrics` | Standard Metrics OAuth client id. |
| `STANDARD_METRICS_CLIENT_SECRET` | `tools/crypto/standard-metrics` | Standard Metrics OAuth client secret. |
| `SYNOPTIC_API_KEY` | `tools/comms/twitter` | Synoptic/Twitter API access. |
| `TALLY_API_KEY` | `tools/crypto/tally` | Tally API access. |
| `TELEGRAM_BOT_TOKEN` | `tools/comms/telegram` | Telegram Bot API access. |
| `TOKENOMIST_API_KEY` | `tools/crypto/tokenomist` | Tokenomist API access. |
| `TOKEN_TERMINAL_API_KEY` | `tools/crypto/token-terminal` | Token Terminal API access. |
| `YOUTUBE_API_KEY` | `tools/research/youtube` | YouTube Data API access. |
