import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { deployments, usageEvents } from "@/lib/schema";
import { and, eq, sql } from "drizzle-orm";

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

  const summary = await db
    .select({
      eventType: usageEvents.eventType,
      total: sql<number>`sum(${usageEvents.count})`.as("total"),
    })
    .from(usageEvents)
    .where(eq(usageEvents.deploymentId, id))
    .groupBy(usageEvents.eventType);

  return NextResponse.json({
    deploymentId: id,
    tier: deployment.tier,
    monthlyCost: deployment.monthlyCost,
    usage: Object.fromEntries(summary.map((s) => [s.eventType, s.total])),
  });
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  // This endpoint is called by the Centaur API to report usage events.
  // Authenticated by a deployment-specific webhook secret, not Clerk.
  const expectedSecret = process.env.CENTAUR_BILLING_EVENTS_SECRET;
  const webhookSecret = request.headers.get("x-webhook-secret");
  if (!expectedSecret || webhookSecret !== expectedSecret) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { event_type, count } = body;

  if (!event_type) {
    return NextResponse.json({ error: "event_type is required" }, { status: 400 });
  }

  await db.insert(usageEvents).values({
    deploymentId: id,
    eventType: event_type,
    count: count ?? 1,
  });

  return NextResponse.json({ ok: true });
}
