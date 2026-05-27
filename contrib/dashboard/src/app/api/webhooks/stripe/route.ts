import { NextResponse } from "next/server";
import { stripe } from "@/lib/stripe";
import { db } from "@/lib/db";
import { billingCustomers, deployments, stripeWebhookEvents } from "@/lib/schema";
import { eq } from "drizzle-orm";
import { logger } from "@/lib/logger";
import { appendCreditLedgerEntry, upsertSubscriptionFromStripe } from "@/lib/billing";

export async function POST(request: Request) {
  const body = await request.text();
  const sig = request.headers.get("stripe-signature");

  if (!sig) {
    return NextResponse.json({ error: "Missing signature" }, { status: 400 });
  }

  if (!stripe) {
    return NextResponse.json({ error: "Stripe not configured" }, { status: 503 });
  }
  if (!process.env.STRIPE_WEBHOOK_SECRET) {
    return NextResponse.json({ error: "Stripe webhook secret not configured" }, { status: 503 });
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

  const [seen] = await db
    .insert(stripeWebhookEvents)
    .values({ id: event.id, eventType: event.type })
    .onConflictDoNothing()
    .returning();

  if (!seen) {
    return NextResponse.json({ received: true, duplicate: true });
  }

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object;
      const userId = session.metadata?.user_id;
      const customerId =
        typeof session.customer === "string" ? session.customer : session.customer?.id;
      if (userId && customerId) {
        await db
          .insert(billingCustomers)
          .values({
            userId,
            stripeCustomerId: customerId,
            email: session.customer_details?.email ?? session.customer_email ?? null,
          })
          .onConflictDoUpdate({
            target: billingCustomers.userId,
            set: {
              stripeCustomerId: customerId,
              email: session.customer_details?.email ?? session.customer_email ?? null,
              updatedAt: new Date(),
            },
          });
      }

      if (session.metadata?.checkout_kind === "inference_credits" && userId) {
        const amountCents = Number.parseInt(
          session.metadata.credit_amount_cents || String(session.amount_total || 0),
          10
        );
        await appendCreditLedgerEntry({
          userId,
          stripeCustomerId: customerId ?? null,
          stripeEventId: event.id,
          source: "stripe_checkout_credits",
          amountCents,
          description: session.metadata.credit_pack
            ? `Stripe credit pack: ${session.metadata.credit_pack}`
            : "Stripe inference credits",
        });
        logger.info("stripe_credits_purchased", { userId, amountCents });
        break;
      }

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

    case "customer.subscription.created":
    case "customer.subscription.updated": {
      await upsertSubscriptionFromStripe(event.data.object);
      break;
    }

    case "customer.subscription.deleted": {
      const subscription = event.data.object;
      await upsertSubscriptionFromStripe(subscription);
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

    case "invoice.payment_failed": {
      const invoice = event.data.object;
      const subscriptionId =
        typeof invoice.parent?.subscription_details?.subscription === "string"
          ? invoice.parent.subscription_details.subscription
          : null;
      logger.warn("stripe_invoice_payment_failed", { subscriptionId });
      break;
    }
  }

  return NextResponse.json({ received: true });
}
