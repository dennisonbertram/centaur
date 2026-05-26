import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { deployments } from "@/lib/schema";
import { sql } from "drizzle-orm";

export async function GET() {
  const checks: Record<string, { status: string; detail?: string }> = {};

  // Database check
  try {
    const [result] = await db
      .select({ count: sql<number>`count(*)` })
      .from(deployments);
    checks.database = { status: "ok", detail: `${result.count} deployments` };
  } catch (err) {
    checks.database = {
      status: "error",
      detail: err instanceof Error ? err.message : "Unknown error",
    };
  }

  // Provisioner check
  checks.provisioner = process.env.HCLOUD_TOKEN
    ? { status: "ok", detail: "HCLOUD_TOKEN configured" }
    : { status: "degraded", detail: "HCLOUD_TOKEN not set — provisioning will fail" };

  // Stripe check
  checks.stripe = process.env.STRIPE_SECRET_KEY
    ? { status: "ok" }
    : { status: "degraded", detail: "STRIPE_SECRET_KEY not set — billing disabled" };

  // Clerk check
  checks.clerk = process.env.CLERK_SECRET_KEY
    ? { status: "ok" }
    : { status: "error", detail: "CLERK_SECRET_KEY not set" };

  const overall = Object.values(checks).some((c) => c.status === "error")
    ? "error"
    : Object.values(checks).some((c) => c.status === "degraded")
      ? "degraded"
      : "ok";

  return NextResponse.json(
    { status: overall, checks, timestamp: new Date().toISOString() },
    { status: overall === "error" ? 503 : 200 }
  );
}
