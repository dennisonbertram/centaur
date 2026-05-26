import { auth } from "@clerk/nextjs/server";
import { redirect, notFound } from "next/navigation";
import { randomUUID } from "crypto";
import { db } from "@/lib/db";
import { apiKeys, deployments, credentials } from "@/lib/schema";
import { and, eq, inArray, isNotNull, isNull } from "drizzle-orm";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { SetupWizard } from "./setup-wizard";
import { DeleteButton } from "./delete-button";
import { KeyManagement } from "./key-management";
import { DEFAULT_API_KEY_NAME, hashApiKey, keyPrefix } from "@/lib/api-keys";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  running: "default",
  provisioning: "secondary",
  claiming: "secondary",
  error: "destructive",
  stopped: "outline",
  stopping: "outline",
};

export default async function DeploymentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { userId } = await auth();
  if (!userId) redirect("/sign-in");

  const { id } = await params;

  const [deployment] = await db
    .select()
    .from(deployments)
    .where(and(eq(deployments.id, id), eq(deployments.userId, userId)));

  if (!deployment) notFound();

  if (deployment.apiKey) {
    const existingKeys = await db
      .select({ id: apiKeys.id })
      .from(apiKeys)
      .where(eq(apiKeys.deploymentId, id))
      .limit(1);

    if (existingKeys.length === 0) {
      await db
        .insert(apiKeys)
        .values({
          id: randomUUID(),
          deploymentId: id,
          keyPrefix: keyPrefix(deployment.apiKey),
          keyHash: hashApiKey(deployment.apiKey),
          name: DEFAULT_API_KEY_NAME,
        })
        .onConflictDoNothing();
    }

    await db
      .update(deployments)
      .set({ apiKey: null, updatedAt: new Date() })
      .where(eq(deployments.id, id));
  }

  const creds = await db
    .select()
    .from(credentials)
    .where(eq(credentials.deploymentId, id));

  const activeKeys = await db
    .select({
      id: apiKeys.id,
      keyPrefix: apiKeys.keyPrefix,
      name: apiKeys.name,
      createdAt: apiKeys.createdAt,
      lastUsedAt: apiKeys.lastUsedAt,
    })
    .from(apiKeys)
    .where(and(eq(apiKeys.deploymentId, id), isNull(apiKeys.revokedAt)));

  const revealRows = await db
    .select({
      id: apiKeys.id,
      keyPrefix: apiKeys.keyPrefix,
      name: apiKeys.name,
      revealValue: apiKeys.revealValue,
    })
    .from(apiKeys)
    .where(and(
      eq(apiKeys.deploymentId, id),
      isNull(apiKeys.revokedAt),
      isNotNull(apiKeys.revealValue)
    ));

  if (revealRows.length > 0) {
    await db
      .update(apiKeys)
      .set({ revealValue: null })
      .where(inArray(apiKeys.id, revealRows.map((key) => key.id)));
  }

  const credMap: Record<string, { masked: string; isSet: boolean }> = {};
  for (const c of creds) {
    credMap[c.name] = { masked: c.valueMasked, isSet: c.isSet === 1 };
  }

  const isProvisioning =
    deployment.status === "provisioning" || deployment.status === "claiming";

  return (
    <>
      {isProvisioning && <meta httpEquiv="refresh" content="5" />}

      <div className="space-y-8">
        {/* Breadcrumb */}
        <div>
          <Link
            href="/deployments"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            &larr; Back to deployments
          </Link>
        </div>

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1 flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">
                {deployment.name}
              </h1>
              <Badge variant={STATUS_VARIANT[deployment.status] ?? "outline"}>
                {isProvisioning && (
                  <span className="mr-1.5 inline-block h-2 w-2 animate-pulse rounded-full bg-current" />
                )}
                {deployment.status}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              {deployment.tier} &middot; {deployment.location} &middot;{" "}
              {deployment.monthlyCost}
            </p>
          </div>
          <DeleteButton deploymentId={deployment.id} status={deployment.status} />
        </div>

        {/* Status messages */}
        {deployment.status === "error" && deployment.errorMessage && (
          <Card className="border-destructive/50 bg-destructive/5">
            <CardContent className="pt-6">
              <p className="text-sm font-medium text-destructive">
                Provisioning failed
              </p>
              <p className="mt-2 text-xs font-mono text-destructive/80 break-all">
                {deployment.errorMessage}
              </p>
            </CardContent>
          </Card>
        )}

        {isProvisioning && (
          <Card className="border-yellow-500/30 bg-yellow-500/5">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <span className="relative flex h-3 w-3">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-yellow-400 opacity-75" />
                  <span className="relative inline-flex h-3 w-3 rounded-full bg-yellow-500" />
                </span>
                <div>
                  <p className="text-sm font-medium">
                    Setting up your deployment...
                  </p>
                  <p className="text-xs text-muted-foreground">
                    This usually takes 30–60 seconds. The page updates
                    automatically.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Setup wizard */}
        {deployment.status === "running" && (
          <SetupWizard
            deploymentId={deployment.id}
            ip={deployment.ip}
            webhookUrl={deployment.loadBalancerIp}
            credentials={credMap}
          />
        )}

        {deployment.status === "running" && (
          <KeyManagement
            deploymentId={deployment.id}
            initialKeys={activeKeys.map((key) => ({
              ...key,
              createdAt: key.createdAt.toISOString(),
              lastUsedAt: key.lastUsedAt?.toISOString() ?? null,
            }))}
            initialRevealedKeys={revealRows
              .filter((key) => key.revealValue)
              .map((key) => ({
                id: key.id,
                key: key.revealValue as string,
                name: key.name,
                keyPrefix: key.keyPrefix,
              }))}
          />
        )}

        {/* Connection details */}
        {deployment.status === "running" && (
          <>
            <Separator />
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Connection details</CardTitle>
                <CardDescription>
                  Use these values to connect to your Centaur instance
                  programmatically.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="grid gap-4 text-sm">
                  <div className="flex items-center justify-between py-1">
                    <dt className="text-muted-foreground">Cluster IP</dt>
                    <dd className="font-mono text-xs">{deployment.ip}</dd>
                  </div>
                  <Separator />
                  {deployment.loadBalancerIp && (
                    <>
                      <div className="flex items-center justify-between py-1">
                        <dt className="text-muted-foreground">
                          Slack Webhook URL
                        </dt>
                        <dd className="font-mono text-xs text-right max-w-[50%] break-all">
                          {deployment.loadBalancerIp}
                        </dd>
                      </div>
                      <Separator />
                    </>
                  )}
                  <div className="flex items-center justify-between py-1">
                    <dt className="text-muted-foreground">Namespace</dt>
                    <dd className="font-mono text-xs">
                      centaur-{deployment.id}
                    </dd>
                  </div>
                </dl>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </>
  );
}
