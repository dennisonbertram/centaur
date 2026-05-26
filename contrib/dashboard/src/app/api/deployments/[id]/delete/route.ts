import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { deployments } from "@/lib/schema";
import { and, eq } from "drizzle-orm";
import { logger } from "@/lib/logger";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await params;

  const [deployment] = await db
    .select()
    .from(deployments)
    .where(and(eq(deployments.id, id), eq(deployments.userId, userId)));

  if (!deployment) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  // Set to stopping — the provisioner worker will destroy the K8s resources.
  // For dev: if it's already in error/stopped, just delete the DB record.
  if (deployment.status === "error" || deployment.status === "stopped") {
    await db
      .delete(deployments)
      .where(eq(deployments.id, id));
    logger.info("deployment_deleted", { id, status: deployment.status });
  } else {
    await db
      .update(deployments)
      .set({ status: "stopping", updatedAt: new Date() })
      .where(eq(deployments.id, id));
    logger.info("deployment_stopping", { id });
  }

  return NextResponse.json({ ok: true });
}
