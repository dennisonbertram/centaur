import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { deployments, credentials } from "@/lib/schema";
import { and, eq } from "drizzle-orm";
import { logger } from "@/lib/logger";

export async function GET(
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

  const creds = await db
    .select()
    .from(credentials)
    .where(eq(credentials.deploymentId, id));

  return NextResponse.json(creds);
}

export async function PUT(
  request: Request,
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

  const body = await request.json();
  const { name, value } = body;

  if (!name || !value) {
    return NextResponse.json({ error: "name and value are required" }, { status: 400 });
  }

  const masked = value.slice(0, 6) + "..." + value.slice(-4);

  // Store masked value in the dashboard DB.
  // The provisioner worker handles pushing secrets to K8s clusters —
  // the dashboard does not have kubectl access.
  // Store raw value as pendingValue — the provisioner worker picks it up
  // and pushes it to the K8s cluster, then clears pendingValue.
  await db
    .insert(credentials)
    .values({
      deploymentId: id,
      name,
      valueMasked: masked,
      pendingValue: value,
      isSet: 1,
    })
    .onConflictDoUpdate({
      target: [credentials.deploymentId, credentials.name],
      set: {
        valueMasked: masked,
        pendingValue: value,
        isSet: 1,
        updatedAt: new Date(),
      },
    });

  logger.info("credential_saved", { deploymentId: id, name, userId });

  return NextResponse.json({ name, masked, isSet: true });
}
