import { NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { getCreditBalanceCents } from "@/lib/billing";
import { db } from "@/lib/db";
import { deployments } from "@/lib/schema";

export async function POST(request: Request) {
  const expectedSecret = process.env.CENTAUR_BILLING_EVENTS_SECRET;
  const providedSecret = request.headers.get("x-centaur-billing-secret");
  if (!expectedSecret || providedSecret !== expectedSecret) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json().catch(() => ({}));
  const deploymentId = String(body.deployment_id || "");
  const minimumCreditCents = Math.max(1, Math.round(Number(body.minimum_credit_cents ?? 1)));
  if (!deploymentId) {
    return NextResponse.json({ error: "deployment_id is required" }, { status: 400 });
  }

  const [deployment] = await db
    .select()
    .from(deployments)
    .where(and(eq(deployments.id, deploymentId), eq(deployments.inferenceMode, "managed")))
    .limit(1);

  if (!deployment) {
    return NextResponse.json({ error: "Managed inference is not enabled" }, { status: 404 });
  }

  const balanceCents = await getCreditBalanceCents(deployment.userId);
  return NextResponse.json({
    allowed: balanceCents >= minimumCreditCents,
    balance_cents: balanceCents,
    minimum_credit_cents: minimumCreditCents,
  });
}
