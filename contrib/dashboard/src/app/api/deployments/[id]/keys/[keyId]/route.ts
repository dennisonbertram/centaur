import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { and, eq, isNull } from "drizzle-orm";
import { db } from "@/lib/db";
import { apiKeys, deployments } from "@/lib/schema";
import { canRevokeActiveKey } from "@/lib/api-keys";
import { logger } from "@/lib/logger";

async function loadOwnedDeployment(id: string, userId: string) {
  const [deployment] = await db
    .select({ id: deployments.id })
    .from(deployments)
    .where(and(eq(deployments.id, id), eq(deployments.userId, userId)));
  return deployment ?? null;
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string; keyId: string }> }
) {
  const { userId } = await auth();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id, keyId } = await params;
  const deployment = await loadOwnedDeployment(id, userId);
  if (!deployment) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const activeKeys = await db
    .select({ id: apiKeys.id })
    .from(apiKeys)
    .where(and(eq(apiKeys.deploymentId, id), isNull(apiKeys.revokedAt)));

  if (!activeKeys.some((key) => key.id === keyId)) {
    return NextResponse.json({ error: "Key not found" }, { status: 404 });
  }

  if (!canRevokeActiveKey(activeKeys.length)) {
    return NextResponse.json(
      { error: "Create a replacement key before revoking the last active key." },
      { status: 400 }
    );
  }

  await db
    .update(apiKeys)
    .set({
      revokedAt: new Date(),
      revocationPushedAt: null,
    })
    .where(and(
      eq(apiKeys.id, keyId),
      eq(apiKeys.deploymentId, id),
      isNull(apiKeys.revokedAt)
    ));

  logger.info("deployment_api_key_revoked", {
    deploymentId: id,
    keyId,
    userId,
  });

  return NextResponse.json({ ok: true });
}
