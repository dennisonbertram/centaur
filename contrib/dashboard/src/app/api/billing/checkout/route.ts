import { auth, currentUser } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { ensureStripeCustomer, managedInferenceEnabled } from "@/lib/billing";
import { deployments } from "@/lib/schema";
import { CREDIT_PACKS, stripe, TIER_PRICES } from "@/lib/stripe";

function originFromRequest(request: Request): string {
  const configured = process.env.NEXT_PUBLIC_APP_URL || process.env.APP_URL;
  if (configured) return configured.replace(/\/$/, "");
  return new URL(request.url).origin;
}

export async function POST(request: Request) {
  const { userId } = await auth();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!stripe) return NextResponse.json({ error: "Stripe not configured" }, { status: 503 });
  if (!managedInferenceEnabled()) {
    return NextResponse.json({ error: "Managed inference is disabled" }, { status: 403 });
  }

  const body = await request.json().catch(() => ({}));
  const checkoutKind = String(body.kind || "");
  const user = await currentUser();
  const email = user?.primaryEmailAddress?.emailAddress ?? null;
  const customer = await ensureStripeCustomer({ userId, email });
  const origin = originFromRequest(request);

  if (checkoutKind === "credits") {
    const packId = String(body.pack || "starter");
    const pack = CREDIT_PACKS[packId];
    if (!pack) return NextResponse.json({ error: "Unknown credit pack" }, { status: 400 });

    const session = await stripe.checkout.sessions.create({
      mode: "payment",
      customer,
      client_reference_id: userId,
      success_url: `${origin}/usage?checkout=credits-success`,
      cancel_url: `${origin}/usage?checkout=credits-cancelled`,
      line_items: [
        {
          quantity: 1,
          price_data: {
            currency: "usd",
            unit_amount: pack.amountCents,
            product_data: { name: pack.label },
          },
        },
      ],
      metadata: {
        checkout_kind: "inference_credits",
        user_id: userId,
        credit_amount_cents: String(pack.amountCents),
        credit_pack: packId,
      },
      payment_intent_data: {
        metadata: {
          checkout_kind: "inference_credits",
          user_id: userId,
          credit_amount_cents: String(pack.amountCents),
          credit_pack: packId,
        },
      },
    }, { idempotencyKey: `credits:${userId}:${packId}:${Date.now()}` });

    return NextResponse.json({ url: session.url });
  }

  if (checkoutKind === "subscription") {
    const deploymentId = String(body.deploymentId || "");
    const [deployment] = await db
      .select()
      .from(deployments)
      .where(and(eq(deployments.id, deploymentId), eq(deployments.userId, userId)))
      .limit(1);
    if (!deployment) return NextResponse.json({ error: "Deployment not found" }, { status: 404 });

    const tier = TIER_PRICES[deployment.tier];
    if (!tier || tier.priceId.includes("placeholder")) {
      return NextResponse.json({ error: "Stripe price not configured for tier" }, { status: 503 });
    }

    const session = await stripe.checkout.sessions.create({
      mode: "subscription",
      customer,
      client_reference_id: deployment.id,
      success_url: `${origin}/deployments/${deployment.id}?checkout=subscription-success`,
      cancel_url: `${origin}/deployments/${deployment.id}?checkout=subscription-cancelled`,
      line_items: [{ price: tier.priceId, quantity: 1 }],
      metadata: {
        checkout_kind: "deployment_subscription",
        user_id: userId,
        deployment_id: deployment.id,
      },
      subscription_data: {
        metadata: {
          user_id: userId,
          deployment_id: deployment.id,
        },
      },
    }, { idempotencyKey: `deployment-subscription:${deployment.id}` });

    return NextResponse.json({ url: session.url });
  }

  return NextResponse.json({ error: "kind must be credits or subscription" }, { status: 400 });
}
