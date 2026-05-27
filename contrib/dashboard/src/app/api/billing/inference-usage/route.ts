import { NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { billingSecretConfigured, dollarsToMicros, recordInferenceUsage } from "@/lib/billing";
import { deployments } from "@/lib/schema";

function unauthorized() {
  return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
}

export async function POST(request: Request) {
  const expectedSecret = process.env.CENTAUR_BILLING_EVENTS_SECRET;
  if (!billingSecretConfigured()) {
    return NextResponse.json({ error: "Billing events are not configured" }, { status: 503 });
  }
  const providedSecret = request.headers.get("x-centaur-billing-secret");
  if (!providedSecret || providedSecret !== expectedSecret) return unauthorized();

  const body = await request.json().catch(() => ({}));
  const deploymentId = String(body.deployment_id || "");
  const idempotencyKey = String(body.idempotency_key || "");
  if (!deploymentId || !idempotencyKey) {
    return NextResponse.json(
      { error: "deployment_id and idempotency_key are required" },
      { status: 400 }
    );
  }

  const [deployment] = await db
    .select()
    .from(deployments)
    .where(and(eq(deployments.id, deploymentId), eq(deployments.inferenceMode, "managed")))
    .limit(1);

  if (!deployment) {
    return NextResponse.json({ error: "Managed inference is not enabled" }, { status: 404 });
  }

  const providerCostMicros =
    Number.isFinite(Number(body.provider_cost_micros))
      ? Math.round(Number(body.provider_cost_micros))
      : dollarsToMicros(Number(body.cost_usd ?? 0));

  const result = await recordInferenceUsage({
    idempotencyKey,
    userId: deployment.userId,
    deploymentId,
    executionId: body.execution_id ? String(body.execution_id) : null,
    eventId: Number.isFinite(Number(body.event_id)) ? Number(body.event_id) : null,
    model: body.model ? String(body.model) : null,
    inputTokens: Number(body.input_tokens ?? 0),
    outputTokens: Number(body.output_tokens ?? 0),
    cacheCreationInputTokens: Number(body.cache_creation_input_tokens ?? 0),
    cacheReadInputTokens: Number(body.cache_read_input_tokens ?? 0),
    providerCostMicros,
  });

  return NextResponse.json({
    ok: true,
    usage_event_id: result.usage?.id ?? null,
    duplicate: !result.inserted,
  });
}
