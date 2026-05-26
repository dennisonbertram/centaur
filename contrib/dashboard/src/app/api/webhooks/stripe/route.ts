import { NextResponse } from "next/server";
import { stripe } from "@/lib/stripe";
import { db } from "@/lib/db";
import { deployments } from "@/lib/schema";
import { eq } from "drizzle-orm";
import { logger } from "@/lib/logger";

export async function POST(request: Request) {
  const body = await request.text();
  const sig = request.headers.get("stripe-signature");

  if (!sig) {
    return NextResponse.json({ error: "Missing signature" }, { status: 400 });
  }

  if (!stripe) {
    return NextResponse.json({ error: "Stripe not configured" }, { status: 503 });
  }

  let event;
  try {
    event = stripe.webhooks.constructEvent(
      body,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch {
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object;
      const deploymentId = session.metadata?.deployment_id;

      if (deploymentId) {
        logger.info("stripe_checkout_completed", { deploymentId });

        // Set status=provisioning — the provisioner worker picks it up
        await db
          .update(deployments)
          .set({ status: "provisioning", updatedAt: new Date() })
          .where(eq(deployments.id, deploymentId));
      }
      break;
    }

    case "customer.subscription.deleted": {
      const subscription = event.data.object;
      const deploymentId = subscription.metadata?.deployment_id;

      if (deploymentId) {
        logger.info("stripe_subscription_deleted", { deploymentId });

        // Set status=stopping — the provisioner worker picks it up
        await db
          .update(deployments)
          .set({ status: "stopping", updatedAt: new Date() })
          .where(eq(deployments.id, deploymentId));
      }
      break;
    }
  }

  return NextResponse.json({ received: true });
}
