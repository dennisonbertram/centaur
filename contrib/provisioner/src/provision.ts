import { execFileSync } from "child_process";
import { writeFileSync, mkdirSync, existsSync, readFileSync } from "fs";
import { join } from "path";
import { log } from "./log.js";

const STATE_DIR = process.env.CENTAUR_STATE_DIR || "/tmp/deployments";
const CHART_PATH = process.env.CENTAUR_CHART_PATH || "/app/chart";
const MODE = process.env.CENTAUR_PROVISION_MODE || "shared";

const NAME_RE = /^[a-z0-9][a-z0-9-]{0,18}[a-z0-9]$/;

function resolveKubeconfig(): string | null {
  const path = process.env.SHARED_CLUSTER_KUBECONFIG;
  if (path && existsSync(path)) return path;

  const b64 = process.env.SHARED_CLUSTER_KUBECONFIG_B64;
  if (b64) {
    const decoded = Buffer.from(b64, "base64").toString("utf-8");
    const tmpPath = "/tmp/shared-kubeconfig.yaml";
    writeFileSync(tmpPath, decoded, { mode: 0o600 });
    return tmpPath;
  }
  return null;
}

export type ProvisionResult = {
  success: boolean;
  ip?: string;
  loadBalancerIp?: string;
  apiKey?: string;
  error?: string;
};

function redactError(msg: string): string {
  return msg
    .replace(/sk-[A-Za-z0-9_-]{10,}/g, "sk-***")
    .replace(/xoxb-[A-Za-z0-9-]+/g, "xoxb-***")
    .replace(/postgresql:\/\/[^@]+@/g, "postgresql://***@")
    .replace(/-----BEGIN[^-]+-----[\s\S]*?-----END[^-]+-----/g, "[REDACTED_KEY]")
    .slice(0, 500);
}

function kubectl(args: string[], env: Record<string, string>): string {
  return execFileSync("kubectl", args, {
    encoding: "utf-8",
    timeout: 60_000,
    env: { ...process.env, ...env },
    stdio: ["pipe", "pipe", "pipe"],
  }).trim();
}

function helm(args: string[], env: Record<string, string>): string {
  return execFileSync("helm", args, {
    encoding: "utf-8",
    timeout: 300_000,
    env: { ...process.env, ...env },
    stdio: ["pipe", "pipe", "pipe"],
  }).trim();
}

function secretExists(ns: string, name: string, env: Record<string, string>): boolean {
  try {
    kubectl(["-n", ns, "get", "secret", name, "-o", "name"], env);
    return true;
  } catch {
    return false;
  }
}

function getSecretValue(ns: string, secretName: string, key: string, env: Record<string, string>): string | null {
  try {
    const b64 = kubectl(
      ["-n", ns, "get", "secret", secretName, "-o", `jsonpath={.data.${key}}`],
      env
    );
    return Buffer.from(b64, "base64").toString("utf-8");
  } catch {
    return null;
  }
}

function applySecretYaml(ns: string, name: string, data: Record<string, string>, env: Record<string, string>) {
  const b64Data: Record<string, string> = {};
  for (const [k, v] of Object.entries(data)) {
    b64Data[k] = Buffer.from(v).toString("base64");
  }
  const yaml = JSON.stringify({
    apiVersion: "v1",
    kind: "Secret",
    metadata: { name, namespace: ns },
    data: b64Data,
  });
  execFileSync("kubectl", ["apply", "-f", "-"], {
    input: yaml,
    encoding: "utf-8",
    timeout: 30_000,
    env: { ...process.env, ...env },
    stdio: ["pipe", "pipe", "pipe"],
  });
}

function sharedClusterProvision(params: {
  name: string;
  slug: string;
  tier: string;
  location: string;
}): ProvisionResult {
  const kubeconfig = resolveKubeconfig();
  if (!kubeconfig) {
    return { success: false, error: "SHARED_CLUSTER_KUBECONFIG or SHARED_CLUSTER_KUBECONFIG_B64 not set" };
  }

  if (!NAME_RE.test(params.name)) {
    return { success: false, error: `Invalid deployment name: ${params.name}` };
  }

  const ns = `centaur-${params.name}`;
  const env = { KUBECONFIG: kubeconfig };

  try {
    // Phase 1: Create namespace (idempotent)
    kubectl(["create", "namespace", ns, "--dry-run=client", "-o", "yaml"], env);
    const nsYaml = kubectl(["create", "namespace", ns, "--dry-run=client", "-o", "yaml"], env);
    execFileSync("kubectl", ["apply", "-f", "-"], {
      input: nsYaml,
      encoding: "utf-8",
      timeout: 30_000,
      env: { ...process.env, ...env },
      stdio: ["pipe", "pipe", "pipe"],
    });
    log("namespace_created", { namespace: ns });

    // Phase 2: Create or reuse secrets (idempotent — don't regenerate on retry)
    let pgPass: string;
    let devApiKey: string;

    if (secretExists(ns, "centaur-infra-env", env)) {
      log("secrets_reused", { namespace: ns });
      pgPass = getSecretValue(ns, "centaur-infra-env", "POSTGRES_PASSWORD", env) || "";
      devApiKey = getSecretValue(ns, "centaur-infra-env", "LOCAL_DEV_API_KEY", env) || "";
    } else {
      pgPass = execFileSync("openssl", ["rand", "-hex", "24"], { encoding: "utf-8" }).trim();
      const ironKey = execFileSync("openssl", ["rand", "-hex", "32"], { encoding: "utf-8" }).trim();
      const sandboxKey = execFileSync("openssl", ["rand", "-hex", "32"], { encoding: "utf-8" }).trim();
      const slackbotKey = execFileSync("openssl", ["rand", "-hex", "24"], { encoding: "utf-8" }).trim();
      devApiKey = `centaur-${params.name}-${execFileSync("openssl", ["rand", "-hex", "16"], { encoding: "utf-8" }).trim()}`;
      const pgSvc = `${params.name}-centaur-postgres`;
      const dbUrl = `postgresql://tempo:${pgPass}@${pgSvc}:5432/ai_v2`;

      const secretData: Record<string, string> = {
        POSTGRES_PASSWORD: pgPass,
        DATABASE_URL: dbUrl,
        IRON_MANAGEMENT_API_KEY: ironKey,
        SANDBOX_SIGNING_KEY: sandboxKey,
        SLACKBOT_API_KEY: slackbotKey,
        LOCAL_DEV_API_KEY: devApiKey,
        SLACK_BOT_TOKEN: "stub",
        SLACK_SIGNING_SECRET: "stub",
        OP_SERVICE_ACCOUNT_TOKEN: "unused",
        OP_VAULT: "unused",
      };
      if (process.env.OPENAI_API_KEY) secretData.OPENAI_API_KEY = process.env.OPENAI_API_KEY;
      if (process.env.ANTHROPIC_API_KEY) secretData.ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;

      applySecretYaml(ns, "centaur-infra-env", secretData, env);

      // Generate CA
      const tmpDir = join(STATE_DIR, params.name, "ca");
      mkdirSync(tmpDir, { recursive: true });
      execFileSync("openssl", ["genrsa", "-out", `${tmpDir}/ca-key.pem`, "4096"], { stdio: "pipe" });
      execFileSync("openssl", [
        "req", "-x509", "-new", "-nodes",
        "-key", `${tmpDir}/ca-key.pem`,
        "-sha256", "-days", "3650",
        "-subj", "/CN=centaur iron-proxy CA",
        "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,keyCertSign",
        "-out", `${tmpDir}/ca-cert.pem`,
      ], { stdio: "pipe" });
      const caCert = readFileSync(`${tmpDir}/ca-cert.pem`, "utf-8");
      const caKey = readFileSync(`${tmpDir}/ca-key.pem`, "utf-8");

      applySecretYaml(ns, "centaur-firewall-ca", { "ca-cert.pem": caCert }, env);
      applySecretYaml(ns, "centaur-firewall-ca-key", { "ca-cert.pem": caCert, "ca-key.pem": caKey }, env);

      log("secrets_created", { namespace: ns });
    }

    // Phase 3: Deploy Centaur via Helm (idempotent — upgrade --install)
    const registry = process.env.CENTAUR_IMAGE_REGISTRY || "docker.io/library/centaur";
    const tag = process.env.CENTAUR_IMAGE_TAG || "amd64";
    const pullPolicy = process.env.CENTAUR_IMAGE_PULL_POLICY || "Never";

    helm(["dependency", "update", CHART_PATH], env);
    helm([
      "upgrade", "--install", params.name, CHART_PATH,
      "-n", ns,
      "--set", `api.image.repository=${registry}-api`,
      "--set", `api.image.tag=${tag}`,
      "--set", `api.image.pullPolicy=${pullPolicy}`,
      "--set", "api.executionWorkerEnabled=true",
      "--set", "api.egressDiscovery.enabled=false",
      "--set", `sandbox.image.repository=${registry}-agent`,
      "--set", `sandbox.image.tag=${tag}`,
      "--set", `sandbox.image.pullPolicy=${pullPolicy}`,
      "--set", `ironProxy.image.repository=${registry}-iron-proxy`,
      "--set", `ironProxy.image.tag=${tag}`,
      "--set", `ironProxy.image.pullPolicy=${pullPolicy}`,
      "--set", "ironProxy.secretSource=env",
      "--set", "slackbot.enabled=true",
      "--set", `slackbot.image.repository=${registry}-slackbot`,
      "--set", `slackbot.image.tag=${tag}`,
      "--set", `slackbot.image.pullPolicy=${pullPolicy}`,
      "--set", "laminar.enabled=false",
      "--set", "secretManager.backend=env",
      "--set", "networkPolicy.enabled=true",
    ], env);
    log("helm_deployed", { namespace: ns, release: params.name });

    // Create Ingress with routes for slackbot AND API (idempotent)
    const domain = process.env.CENTAUR_DOMAIN || "trycentaur.dev";
    const slug = params.slug || params.name;
    if (!/^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(slug)) {
      throw new Error(`Invalid slug for DNS hostname: ${slug}`);
    }
    const hostname = `${slug}.${domain}`;
    const ingressYaml = JSON.stringify({
      apiVersion: "networking.k8s.io/v1",
      kind: "Ingress",
      metadata: {
        name: `${params.name}-ingress`,
        namespace: ns,
        annotations: {
          "cert-manager.io/cluster-issuer": "letsencrypt-prod",
          "traefik.ingress.kubernetes.io/router.entrypoints": "websecure",
        },
      },
      spec: {
        ingressClassName: "traefik",
        tls: [{ hosts: [hostname], secretName: `${params.name}-tls` }],
        rules: [{
          host: hostname,
          http: {
            paths: [
              {
                path: "/api/webhooks/slack",
                pathType: "Prefix",
                backend: {
                  service: { name: `${params.name}-centaur-slackbot`, port: { number: 3001 } },
                },
              },
              {
                path: "/api/slack",
                pathType: "Prefix",
                backend: {
                  service: { name: `${params.name}-centaur-slackbot`, port: { number: 3001 } },
                },
              },
              {
                path: "/",
                pathType: "Prefix",
                backend: {
                  service: { name: `${params.name}-centaur-api`, port: { number: 8000 } },
                },
              },
            ],
          },
        }],
      },
    });
    execFileSync("kubectl", ["apply", "-f", "-"], {
      input: ingressYaml,
      encoding: "utf-8",
      timeout: 30_000,
      env: { ...process.env, ...env },
      stdio: ["pipe", "pipe", "pipe"],
    });
    log("ingress_created", { namespace: ns, host: hostname });

    // Allow Traefik (kube-system) to reach tenant pods
    const traefikPolicy = JSON.stringify({
      apiVersion: "networking.k8s.io/v1",
      kind: "NetworkPolicy",
      metadata: { name: "allow-traefik-ingress", namespace: ns },
      spec: {
        podSelector: {},
        policyTypes: ["Ingress"],
        ingress: [{
          from: [{ namespaceSelector: { matchLabels: { "kubernetes.io/metadata.name": "kube-system" } } }],
          ports: [
            { port: 8000, protocol: "TCP" },
            { port: 3001, protocol: "TCP" },
            { port: 8089, protocol: "TCP" },
          ],
        }],
      },
    });
    execFileSync("kubectl", ["apply", "-f", "-"], {
      input: traefikPolicy,
      encoding: "utf-8",
      timeout: 30_000,
      env: { ...process.env, ...env },
      stdio: ["pipe", "pipe", "pipe"],
    });

    // Allow slackbot to reach Slack API (api.slack.com:443)
    const slackbotEgress = JSON.stringify({
      apiVersion: "networking.k8s.io/v1",
      kind: "NetworkPolicy",
      metadata: { name: "slackbot-egress-internet", namespace: ns },
      spec: {
        podSelector: { matchLabels: { "app.kubernetes.io/component": "slackbot" } },
        policyTypes: ["Egress"],
        egress: [{
          ports: [{ port: 443, protocol: "TCP" }],
          to: [{ ipBlock: { cidr: "0.0.0.0/0" } }],
        }],
      },
    });
    execFileSync("kubectl", ["apply", "-f", "-"], {
      input: slackbotEgress,
      encoding: "utf-8",
      timeout: 30_000,
      env: { ...process.env, ...env },
      stdio: ["pipe", "pipe", "pipe"],
    });

    // Allow API pod to reach K8s API server + remove HTTPS_PROXY
    const apiEgress = JSON.stringify({
      apiVersion: "networking.k8s.io/v1",
      kind: "NetworkPolicy",
      metadata: { name: "api-k8s-access", namespace: ns },
      spec: {
        podSelector: { matchLabels: { "app.kubernetes.io/component": "api" } },
        policyTypes: ["Egress"],
        egress: [
          { to: [{ namespaceSelector: {} }], ports: [{ port: 443, protocol: "TCP" }] },
          { to: [{ ipBlock: { cidr: "0.0.0.0/0" } }], ports: [{ port: 443, protocol: "TCP" }] },
        ],
      },
    });
    execFileSync("kubectl", ["apply", "-f", "-"], {
      input: apiEgress,
      encoding: "utf-8",
      timeout: 30_000,
      env: { ...process.env, ...env },
      stdio: ["pipe", "pipe", "pipe"],
    });

    // Remove HTTPS_PROXY from API and slackbot so they can reach external services directly
    try {
      kubectl(["set", "env", `deployment/${params.name}-centaur-api`, "-n", ns, "--containers=api",
        "HTTPS_PROXY-", "HTTP_PROXY-", "https_proxy-", "http_proxy-"], env);
    } catch (e) {
      log("proxy_removal_failed", { target: "api", error: e instanceof Error ? e.message.slice(0, 100) : String(e) });
    }
    try {
      kubectl(["set", "env", `deployment/${params.name}-centaur-slackbot`, "-n", ns, "--containers=slackbot",
        "HTTPS_PROXY-", "HTTP_PROXY-", "https_proxy-", "http_proxy-"], env);
    } catch (e) {
      log("proxy_removal_failed", { target: "slackbot", error: e instanceof Error ? e.message.slice(0, 100) : String(e) });
    }

    // Phase 4: Apply k3s fixups (idempotent)
    const fixupsPath = join(CHART_PATH, "../hetzner/k8s-fixups.yaml");
    if (existsSync(fixupsPath)) {
      kubectl(["apply", "-n", ns, "-f", fixupsPath], env);
    }

    // Phase 5: Wait for rollout
    kubectl([
      "rollout", "status",
      `deployment/${params.name}-centaur-api`,
      "-n", ns,
      "--timeout=120s",
    ], env);

    const clusterIp = process.env.SHARED_CLUSTER_IP || "unknown";
    const webhookUrl = `https://${slug}.${domain}/api/webhooks/slack`;

    log("provision_complete", {
      name: params.name,
      namespace: ns,
      ip: clusterIp,
      webhookUrl,
    });

    return {
      success: true,
      ip: clusterIp,
      loadBalancerIp: webhookUrl,
      apiKey: devApiKey,
    };
  } catch (err) {
    const raw = err instanceof Error ? err.message : String(err);
    const redacted = redactError(raw);
    log("provision_failed", { name: params.name, error: redacted });
    return { success: false, error: redacted };
  }
}

export function provision(params: {
  name: string;
  slug: string;
  tier: string;
  location: string;
}): ProvisionResult {
  if (!NAME_RE.test(params.name)) {
    return { success: false, error: `Invalid name: must match ${NAME_RE}` };
  }

  log("provision_starting", { ...params, mode: MODE });

  if (MODE === "shared") {
    return sharedClusterProvision(params);
  }

  // Dedicated mode removed per Codex review — not wired through.
  // Use provision.sh directly for dedicated deployments.
  return { success: false, error: "Dedicated mode not available in the worker. Use contrib/hetzner/provision.sh" };
}

export function destroy(name: string): { success: boolean; error?: string } {
  if (!NAME_RE.test(name)) {
    return { success: false, error: `Invalid name: ${name}` };
  }

  log("destroy_starting", { name, mode: MODE });

  if (MODE === "shared") {
    const kubeconfig = resolveKubeconfig();
    if (!kubeconfig) return { success: false, error: "Kubeconfig not configured" };

    const ns = `centaur-${name}`;
    const env = { KUBECONFIG: kubeconfig };

    try {
      // Tolerate missing release
      try {
        helm(["uninstall", name, "-n", ns], env);
      } catch {
        log("destroy_helm_skip", { name, reason: "release not found or already removed" });
      }

      // Tolerate missing/terminating namespace
      try {
        kubectl(["delete", "namespace", ns, "--wait=false"], env);
      } catch {
        log("destroy_ns_skip", { name, reason: "namespace not found or already terminating" });
      }

      log("destroy_complete", { name, namespace: ns });
      return { success: true };
    } catch (err) {
      return { success: false, error: redactError(err instanceof Error ? err.message : String(err)) };
    }
  }

  return { success: false, error: "Dedicated mode destruction not available in worker" };
}
