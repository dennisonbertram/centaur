import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { randomBytes } from "crypto";
import { db } from "@/lib/db";
import { deployments } from "@/lib/schema";
import { eq } from "drizzle-orm";
import { logger } from "@/lib/logger";

export async function POST(request: Request) {
  const { userId } = await auth();
  if (!userId) {
    logger.warn("deployment_create_unauthorized");
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { name, tier, location } = body;

  if (!name || !tier || !location) {
    logger.warn("deployment_create_invalid", { name, tier, location, userId });
    return NextResponse.json(
      { error: "name, tier, and location are required" },
      { status: 400 }
    );
  }

  if (!/^[a-z0-9-]{2,20}$/.test(name)) {
    logger.warn("deployment_create_invalid_name", { name, userId });
    return NextResponse.json(
      { error: "Invalid deployment name" },
      { status: 400 }
    );
  }

  const cost =
    tier === "dev" ? "~$9/mo" : tier === "small" ? "~$82/mo" : "~$136/mo";

  logger.info("deployment_creating", { name, tier, location, userId, cost });

  // Check if name is already taken
  const [existing] = await db
    .select({ id: deployments.id })
    .from(deployments)
    .where(eq(deployments.id, name));

  if (existing) {
    return NextResponse.json(
      { error: `A deployment named "${name}" already exists. Choose a different name.` },
      { status: 409 }
    );
  }

  const slug = randomBytes(8).toString("hex");

  const [deployment] = await db
    .insert(deployments)
    .values({
      id: name,
      userId,
      name,
      tier,
      location,
      slug,
      status: "provisioning",
      monthlyCost: cost,
    })
    .returning();

  // The provisioner worker service polls for status=provisioning and
  // runs Terraform/Helm. The dashboard just records the intent.
  logger.info("deployment_created", {
    id: deployment.id,
    status: "provisioning",
    note: "Provisioner worker will pick this up",
  });

  return NextResponse.json(deployment, { status: 201 });
}

export async function GET() {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const results = await db
    .select()
    .from(deployments)
    .where(eq(deployments.userId, userId))
    .orderBy(deployments.createdAt);

  logger.info("deployments_listed", { userId, count: results.length });
  return NextResponse.json(results);
}
