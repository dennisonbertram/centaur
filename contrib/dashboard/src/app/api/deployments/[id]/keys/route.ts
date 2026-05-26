import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { randomUUID } from "crypto";
import { and, eq, inArray, isNotNull, isNull } from "drizzle-orm";
import { db } from "@/lib/db";
import { apiKeys, deployments } from "@/lib/schema";
import {
  DEFAULT_API_KEY_NAME,
  generateDeploymentApiKey,
  hashApiKey,
  keyPrefix,
  normalizeApiKeyName,
} from "@/lib/api-keys";
import { logger } from "@/lib/logger";

type ApiKeyListItem = {
  id: string;
  keyPrefix: string;
  name: string;
  createdAt: string;
  lastUsedAt: string | null;
};

function serializeKey(row: typeof apiKeys.$inferSelect): ApiKeyListItem {
  return {
    id: row.id,
    keyPrefix: row.keyPrefix,
    name: row.name,
    createdAt: row.createdAt.toISOString(),
    lastUsedAt: row.lastUsedAt?.toISOString() ?? null,
  };
}

async function loadOwnedDeployment(id: string, userId: string) {
  const [deployment] = await db
    .select()
    .from(deployments)
    .where(and(eq(deployments.id, id), eq(deployments.userId, userId)));
  return deployment ?? null;
}

async function migrateLegacyDeploymentKey(deployment: typeof deployments.$inferSelect) {
  if (!deployment.apiKey) return;

  const existing = await db
    .select({ id: apiKeys.id })
    .from(apiKeys)
    .where(eq(apiKeys.deploymentId, deployment.id))
    .limit(1);

  if (existing.length > 0) return;

  await db
    .insert(apiKeys)
    .values({
      id: randomUUID(),
      deploymentId: deployment.id,
      keyPrefix: keyPrefix(deployment.apiKey),
      keyHash: hashApiKey(deployment.apiKey),
      name: DEFAULT_API_KEY_NAME,
    })
    .onConflictDoNothing();

  await db
    .update(deployments)
    .set({ apiKey: null, updatedAt: new Date() })
    .where(eq(deployments.id, deployment.id));

  logger.info("legacy_api_key_migrated", { deploymentId: deployment.id });
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await params;
  const deployment = await loadOwnedDeployment(id, userId);
  if (!deployment) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  await migrateLegacyDeploymentKey(deployment);

  const pendingRevealRows = await db
    .select()
    .from(apiKeys)
    .where(and(
      eq(apiKeys.deploymentId, id),
      isNull(apiKeys.revokedAt),
      isNotNull(apiKeys.revealValue)
    ));

  const revealedKeys = pendingRevealRows
    .filter((row) => row.revealValue)
    .map((row) => ({
      id: row.id,
      key: row.revealValue as string,
      name: row.name,
      keyPrefix: row.keyPrefix,
    }));

  if (pendingRevealRows.length > 0) {
    await db
      .update(apiKeys)
      .set({ revealValue: null })
      .where(inArray(apiKeys.id, pendingRevealRows.map((row) => row.id)));
  }

  const activeKeys = await db
    .select()
    .from(apiKeys)
    .where(and(eq(apiKeys.deploymentId, id), isNull(apiKeys.revokedAt)));

  activeKeys.sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime());

  return NextResponse.json({
    keys: activeKeys.map(serializeKey),
    revealedKeys,
  });
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await params;
  const deployment = await loadOwnedDeployment(id, userId);
  if (!deployment) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const body = await request.json().catch(() => ({}));
  const name = normalizeApiKeyName(body.name);
  const key = generateDeploymentApiKey(id);
  const keyId = randomUUID();
  const now = new Date();

  const [created] = await db
    .insert(apiKeys)
    .values({
      id: keyId,
      deploymentId: id,
      keyPrefix: keyPrefix(key),
      keyHash: hashApiKey(key),
      name,
      pendingValue: key,
      createdAt: now,
    })
    .returning();

  logger.info("deployment_api_key_created", {
    deploymentId: id,
    keyId,
    userId,
  });

  return NextResponse.json({
    key,
    keyRecord: serializeKey(created),
  }, { status: 201 });
}
