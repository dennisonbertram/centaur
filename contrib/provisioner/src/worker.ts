import { db, deployments, credentials, apiKeys } from "./db.js";
import { and, eq, inArray, sql, isNotNull, isNull } from "drizzle-orm";
import { execFileSync } from "child_process";
import { createHash, randomUUID } from "crypto";
import { writeFileSync, existsSync } from "fs";
import { provision, destroy } from "./provision.js";
import { log } from "./log.js";

const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL_MS || "15000", 10);
const WORKER_ID = `worker-${process.pid}-${Date.now()}`;
const API_KEY_SECRET_NAME = "LOCAL_DEV_API_KEY";
const API_KEYS_SECRET_NAME = "LOCAL_DEV_API_KEYS";
const REVOKED_API_KEY_HASHES_SECRET_NAME = "LOCAL_DEV_REVOKED_API_KEY_HASHES";
const MANAGED_INFERENCE_BASE_URL = "http://api:8000/ai-gateway/v1";
const MANAGED_INFERENCE_ANTHROPIC_BASE_URL = "http://api:8000/ai-gateway";

function hashApiKey(key: string): string {
  return createHash("sha256").update(key).digest("hex");
}

function resolveSharedKubeconfig(): string | null {
  const kubeconfigPath = process.env.SHARED_CLUSTER_KUBECONFIG;
  const b64 = process.env.SHARED_CLUSTER_KUBECONFIG_B64;
  if (kubeconfigPath && existsSync(kubeconfigPath)) {
    return kubeconfigPath;
  }
  if (b64) {
    const decoded = Buffer.from(b64, "base64").toString("utf-8");
    const tmpPath = "/tmp/shared-kubeconfig.yaml";
    writeFileSync(tmpPath, decoded, { mode: 0o600 });
    return tmpPath;
  }
  return null;
}

function patchTenantSecret(
  deploymentId: string,
  kubeconfig: string,
  values: Record<string, string>
) {
  const patchData: Record<string, string> = {};
  for (const [name, value] of Object.entries(values)) {
    patchData[name] = Buffer.from(value).toString("base64");
  }
  const patchJson = JSON.stringify({ data: patchData });
  execFileSync("kubectl", [
    "-n",
    `centaur-${deploymentId}`,
    "patch",
    "secret",
    "centaur-infra-env",
    "--type",
    "merge",
    "-p",
    patchJson,
  ], {
    encoding: "utf-8",
    timeout: 15_000,
    env: { ...process.env, KUBECONFIG: kubeconfig },
    stdio: ["pipe", "pipe", "pipe"],
  });
}

function restartTenantApi(deploymentId: string, kubeconfig: string) {
  execFileSync("kubectl", [
    "-n",
    `centaur-${deploymentId}`,
    "rollout",
    "restart",
    "deployment",
    `${deploymentId}-centaur-api`,
  ], {
    encoding: "utf-8",
    timeout: 15_000,
    env: { ...process.env, KUBECONFIG: kubeconfig },
    stdio: "pipe",
  });
}

function managedInferenceSecretValues(deploymentId: string): Record<string, string> {
  const billingEventsUrl = (process.env.CENTAUR_BILLING_EVENTS_URL || "").trim();
  const creditCheckUrl = (process.env.CENTAUR_CREDIT_CHECK_URL || "").trim();
  const billingEventsSecret = (process.env.CENTAUR_BILLING_EVENTS_SECRET || "").trim();
  const aiGatewayApiKey = (process.env.AI_GATEWAY_API_KEY || "").trim();
  const sandboxExtraEnv = [
    { name: "OPENAI_BASE_URL", value: MANAGED_INFERENCE_BASE_URL },
    { name: "ANTHROPIC_BASE_URL", value: MANAGED_INFERENCE_ANTHROPIC_BASE_URL },
  ];
  return {
    CENTAUR_DEPLOYMENT_ID: deploymentId,
    CENTAUR_MANAGED_INFERENCE: "1",
    CENTAUR_AI_GATEWAY_BASE_URL: MANAGED_INFERENCE_BASE_URL,
    AI_GATEWAY_API_KEY: aiGatewayApiKey,
    CENTAUR_BILLING_EVENTS_URL: billingEventsUrl,
    CENTAUR_CREDIT_CHECK_URL: creditCheckUrl,
    CENTAUR_BILLING_EVENTS_SECRET: billingEventsSecret,
    KUBERNETES_SANDBOX_EXTRA_ENV: JSON.stringify(sandboxExtraEnv),
  };
}

async function claimJob(targetStatus: string): Promise<typeof deployments.$inferSelect | null> {
  // Atomic claim: only one worker gets the row
  const [claimed] = await db.execute<typeof deployments.$inferSelect>(sql`
    UPDATE deployments
    SET status = ${targetStatus === "provisioning" ? "claiming" : "claim-stopping"},
        error_message = ${`Claimed by ${WORKER_ID}`},
        updated_at = NOW()
    WHERE id = (
      SELECT id FROM deployments
      WHERE status = ${targetStatus}
      ORDER BY created_at ASC
      LIMIT 1
      FOR UPDATE SKIP LOCKED
    )
    RETURNING *
  `);
  return claimed ?? null;
}

async function processProvision() {
  const job = await claimJob("provisioning");
  if (!job) return;

  log("worker_provisioning", { id: job.id, slug: job.slug, tier: job.tier, location: job.location, worker: WORKER_ID });

  const result = provision({
    name: job.name,
    slug: job.slug || job.name,
    tier: job.tier,
    location: job.location,
  });

  if (result.success) {
    if (job.inferenceMode === "managed") {
      const kubeconfig = resolveSharedKubeconfig();
      if (kubeconfig) {
        try {
          patchTenantSecret(job.id, kubeconfig, managedInferenceSecretValues(job.id));
          restartTenantApi(job.id, kubeconfig);
          log("managed_inference_configured", { id: job.id });
        } catch (err) {
          log("managed_inference_config_failed", {
            id: job.id,
            error: err instanceof Error ? err.message.slice(0, 200) : String(err),
          });
        }
      }
    }

    if (result.apiKey) {
      await db
        .insert(apiKeys)
        .values({
          id: randomUUID(),
          deploymentId: job.id,
          keyPrefix: result.apiKey.slice(0, 12),
          keyHash: hashApiKey(result.apiKey),
          name: "Default",
          revealValue: result.apiKey,
        })
        .onConflictDoNothing();
    }

    await db
      .update(deployments)
      .set({
        status: "running",
        ip: result.ip ?? null,
        loadBalancerIp: result.loadBalancerIp ?? null,
        apiKey: null,
        kubeconfigPath: null, // provisioner owns kubectl, not the dashboard
        errorMessage: null,
        updatedAt: new Date(),
      })
      .where(eq(deployments.id, job.id));

    log("worker_provisioned", { id: job.id, ip: result.ip });
  } else {
    await db
      .update(deployments)
      .set({
        status: "error",
        errorMessage: result.error ?? "Unknown error",
        updatedAt: new Date(),
      })
      .where(eq(deployments.id, job.id));

    log("worker_provision_failed", { id: job.id, error: result.error });
  }
}

async function processDestroy() {
  const job = await claimJob("stopping");
  if (!job) return;

  log("worker_destroying", { id: job.id, worker: WORKER_ID });

  const result = destroy(job.name);

  await db
    .update(deployments)
    .set({
      status: result.success ? "stopped" : "error",
      errorMessage: result.error ?? null,
      updatedAt: new Date(),
    })
    .where(eq(deployments.id, job.id));

  log(result.success ? "worker_destroyed" : "worker_destroy_failed", {
    id: job.id,
    error: result.error,
  });
}

async function processPendingCredentials() {
  // Find credentials with pendingValue that need to be pushed to K8s
  const pending = await db
    .select()
    .from(credentials)
    .where(isNotNull(credentials.pendingValue));

  if (pending.length === 0) return;

  const kubeconfig = resolveSharedKubeconfig();
  if (!kubeconfig) return;

  // Group by deployment
  const byDeployment: Record<string, typeof pending> = {};
  for (const c of pending) {
    if (!byDeployment[c.deploymentId]) byDeployment[c.deploymentId] = [];
    byDeployment[c.deploymentId].push(c);
  }

  for (const [deploymentId, creds] of Object.entries(byDeployment)) {
    const ns = `centaur-${deploymentId}`;
    const env = { KUBECONFIG: kubeconfig };

    // Build patch data
    const patchData: Record<string, string> = {};
    for (const c of creds) {
      if (c.pendingValue) {
        patchData[c.name] = Buffer.from(c.pendingValue).toString("base64");
      }
    }

    try {
      const patchJson = JSON.stringify({ data: patchData });
      execFileSync("kubectl", ["-n", ns, "patch", "secret", "centaur-infra-env", "--type", "merge", "-p", patchJson], {
        encoding: "utf-8",
        timeout: 15_000,
        env: { ...process.env, ...env },
        stdio: ["pipe", "pipe", "pipe"],
      });

      // Restart slackbot and API to pick up new secrets
      try {
        execFileSync("kubectl", ["-n", ns, "rollout", "restart", "deployment", `${deploymentId}-centaur-slackbot`], {
          encoding: "utf-8", timeout: 15_000, env: { ...process.env, ...env }, stdio: "pipe",
        });
      } catch { /* slackbot might not exist */ }

      try {
        execFileSync("kubectl", ["-n", ns, "rollout", "restart", "deployment", `${deploymentId}-centaur-api`], {
          encoding: "utf-8", timeout: 15_000, env: { ...process.env, ...env }, stdio: "pipe",
        });
      } catch { /* ignore */ }

      // Clear pendingValue
      for (const c of creds) {
        await db
          .update(credentials)
          .set({ pendingValue: null, updatedAt: new Date() })
          .where(eq(credentials.id, c.id));
      }

      log("credentials_pushed", {
        deploymentId,
        keys: creds.map(c => c.name),
      });
    } catch (err) {
      log("credentials_push_failed", {
        deploymentId,
        error: err instanceof Error ? err.message.slice(0, 200) : String(err),
      });
    }
  }
}

async function processPendingApiKeys() {
  const pending = await db
    .select()
    .from(apiKeys)
    .where(and(isNotNull(apiKeys.pendingValue), isNull(apiKeys.revokedAt)));

  if (pending.length === 0) return;

  const kubeconfig = resolveSharedKubeconfig();
  if (!kubeconfig) return;

  const byDeployment: Record<string, typeof pending> = {};
  for (const key of pending) {
    if (!byDeployment[key.deploymentId]) byDeployment[key.deploymentId] = [];
    byDeployment[key.deploymentId].push(key);
  }

  for (const [deploymentId, keys] of Object.entries(byDeployment)) {
    const plaintextKeys = keys
      .map((key) => key.pendingValue)
      .filter((value): value is string => !!value);
    if (plaintextKeys.length === 0) continue;

    try {
      patchTenantSecret(deploymentId, kubeconfig, {
        [API_KEY_SECRET_NAME]: plaintextKeys[plaintextKeys.length - 1],
        [API_KEYS_SECRET_NAME]: plaintextKeys.join("\n"),
      });
      restartTenantApi(deploymentId, kubeconfig);

      await db
        .update(apiKeys)
        .set({ pendingValue: null })
        .where(inArray(apiKeys.id, keys.map((key) => key.id)));

      log("api_keys_pushed", {
        deploymentId,
        count: plaintextKeys.length,
      });
    } catch (err) {
      log("api_keys_push_failed", {
        deploymentId,
        error: err instanceof Error ? err.message.slice(0, 200) : String(err),
      });
    }
  }
}

async function processPendingApiKeyRevocations() {
  const pending = await db
    .select()
    .from(apiKeys)
    .where(and(isNotNull(apiKeys.revokedAt), isNull(apiKeys.revocationPushedAt)));

  if (pending.length === 0) return;

  const kubeconfig = resolveSharedKubeconfig();
  if (!kubeconfig) return;

  const deploymentIds = [...new Set(pending.map((key) => key.deploymentId))];

  for (const deploymentId of deploymentIds) {
    const revoked = await db
      .select({ keyHash: apiKeys.keyHash })
      .from(apiKeys)
      .where(and(eq(apiKeys.deploymentId, deploymentId), isNotNull(apiKeys.revokedAt)));

    try {
      patchTenantSecret(deploymentId, kubeconfig, {
        [REVOKED_API_KEY_HASHES_SECRET_NAME]: revoked
          .map((key) => key.keyHash)
          .join("\n"),
      });
      restartTenantApi(deploymentId, kubeconfig);

      await db
        .update(apiKeys)
        .set({ revocationPushedAt: new Date() })
        .where(and(eq(apiKeys.deploymentId, deploymentId), isNotNull(apiKeys.revokedAt)));

      log("api_key_revocations_pushed", {
        deploymentId,
        count: revoked.length,
      });
    } catch (err) {
      log("api_key_revocations_push_failed", {
        deploymentId,
        error: err instanceof Error ? err.message.slice(0, 200) : String(err),
      });
    }
  }
}

async function processBillingOutbox() {
  const processUrl = (process.env.CENTAUR_BILLING_OUTBOX_PROCESS_URL || "").trim();
  const secret = (process.env.CENTAUR_BILLING_EVENTS_SECRET || "").trim();
  if (!processUrl || !secret) return;

  try {
    const response = await fetch(processUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-centaur-billing-secret": secret,
      },
      body: JSON.stringify({ limit: 25 }),
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const result = await response.json().catch(() => ({}));
    if (result.processed || result.failed) {
      log("billing_outbox_processed", result);
    }
  } catch (err) {
    log("billing_outbox_process_failed", {
      error: err instanceof Error ? err.message.slice(0, 200) : String(err),
    });
  }
}

async function tick() {
  await processProvision();
  await processDestroy();
  await processPendingCredentials();
  await processPendingApiKeys();
  await processPendingApiKeyRevocations();
  await processBillingOutbox();
}

async function main() {
  log("worker_starting", {
    workerId: WORKER_ID,
    mode: process.env.CENTAUR_PROVISION_MODE || "shared",
    pollInterval: POLL_INTERVAL,
    hasHcloudToken: !!process.env.HCLOUD_TOKEN,
    hasSharedKubeconfig: !!(process.env.SHARED_CLUSTER_KUBECONFIG || process.env.SHARED_CLUSTER_KUBECONFIG_B64),
  });

  let tickCount = 0;
  while (true) {
    tickCount++;
    try {
      await tick();
      if (tickCount <= 3 || tickCount % 20 === 0) {
        log("worker_heartbeat", { tick: tickCount, worker: WORKER_ID });
      }
    } catch (err) {
      log("worker_tick_error", {
        tick: tickCount,
        error: err instanceof Error ? err.message : String(err),
        stack: err instanceof Error ? err.stack?.split("\n").slice(0, 3).join(" | ") : undefined,
      });
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL));
  }
}

main();
