import { db, deployments, credentials } from "./db.js";
import { eq, sql, isNotNull } from "drizzle-orm";
import { execFileSync } from "child_process";
import { writeFileSync, existsSync } from "fs";
import { provision, destroy } from "./provision.js";
import { log } from "./log.js";

const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL_MS || "15000", 10);
const WORKER_ID = `worker-${process.pid}-${Date.now()}`;

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
    await db
      .update(deployments)
      .set({
        status: "running",
        ip: result.ip ?? null,
        loadBalancerIp: result.loadBalancerIp ?? null,
        apiKey: result.apiKey ?? null,
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

  // Resolve kubeconfig
  const kubeconfigPath = process.env.SHARED_CLUSTER_KUBECONFIG;
  const b64 = process.env.SHARED_CLUSTER_KUBECONFIG_B64;
  let kubeconfig: string | null = null;
  if (kubeconfigPath && existsSync(kubeconfigPath)) {
    kubeconfig = kubeconfigPath;
  } else if (b64) {
    const decoded = Buffer.from(b64, "base64").toString("utf-8");
    const tmpPath = "/tmp/shared-kubeconfig.yaml";
    writeFileSync(tmpPath, decoded, { mode: 0o600 });
    kubeconfig = tmpPath;
  }

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

async function tick() {
  await processProvision();
  await processDestroy();
  await processPendingCredentials();
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
