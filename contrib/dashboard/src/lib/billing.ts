import { randomUUID } from "crypto";
import { and, desc, eq, sql } from "drizzle-orm";
import type Stripe from "stripe";
import { db } from "@/lib/db";
import {
  billingCustomers,
  billingOutboxEvents,
  billingSubscriptions,
  creditLedgerEntries,
  inferenceUsageEvents,
} from "@/lib/schema";
import { stripe } from "@/lib/stripe";
import {
  chargeCentsForProviderCostMicros,
  dollarsToMicros,
  usageMarkupBasisPoints,
} from "@/lib/billing-pricing";

export { chargeCentsForProviderCostMicros, dollarsToMicros, usageMarkupBasisPoints };

export function managedInferenceEnabled(): boolean {
  return process.env.MANAGED_INFERENCE_ENABLED?.toLowerCase() !== "false";
}

export function billingSecretConfigured(): boolean {
  return !!process.env.CENTAUR_BILLING_EVENTS_SECRET;
}

export async function getCreditBalanceCents(userId: string): Promise<number> {
  const [row] = await db
    .select({ total: sql<number>`coalesce(sum(${creditLedgerEntries.amountCents}), 0)` })
    .from(creditLedgerEntries)
    .where(eq(creditLedgerEntries.userId, userId));
  return Number(row?.total ?? 0);
}

export async function appendCreditLedgerEntry(input: {
  userId: string;
  deploymentId?: string | null;
  stripeCustomerId?: string | null;
  stripeEventId?: string | null;
  source: string;
  amountCents: number;
  description?: string | null;
}) {
  const existingBalance = await getCreditBalanceCents(input.userId);
  const balanceAfterCents = existingBalance + input.amountCents;
  const [entry] = await db
    .insert(creditLedgerEntries)
    .values({
      id: randomUUID(),
      userId: input.userId,
      deploymentId: input.deploymentId ?? null,
      stripeCustomerId: input.stripeCustomerId ?? null,
      stripeEventId: input.stripeEventId ?? null,
      source: input.source,
      amountCents: input.amountCents,
      balanceAfterCents,
      description: input.description ?? null,
    })
    .onConflictDoNothing()
    .returning();
  return entry ?? null;
}

export async function ensureStripeCustomer(input: {
  userId: string;
  email?: string | null;
}): Promise<string> {
  const [existing] = await db
    .select()
    .from(billingCustomers)
    .where(eq(billingCustomers.userId, input.userId))
    .limit(1);
  if (existing) return existing.stripeCustomerId;

  if (!stripe) {
    throw new Error("Stripe is not configured");
  }

  const customer = await stripe.customers.create({
    email: input.email ?? undefined,
    metadata: { user_id: input.userId },
  });

  await db
    .insert(billingCustomers)
    .values({
      userId: input.userId,
      stripeCustomerId: customer.id,
      email: input.email ?? null,
    })
    .onConflictDoUpdate({
      target: billingCustomers.userId,
      set: {
        stripeCustomerId: customer.id,
        email: input.email ?? null,
        updatedAt: new Date(),
      },
    });

  return customer.id;
}

export async function upsertSubscriptionFromStripe(subscription: Stripe.Subscription) {
  const deploymentId = subscription.metadata?.deployment_id || null;
  const userId = subscription.metadata?.user_id;
  if (!userId) return;

  const firstItem = subscription.items.data[0];
  const periodEnd = firstItem?.current_period_end
    ? new Date(firstItem.current_period_end * 1000)
    : null;
  const customerId =
    typeof subscription.customer === "string"
      ? subscription.customer
      : subscription.customer.id;

  await db
    .insert(billingSubscriptions)
    .values({
      id: randomUUID(),
      userId,
      deploymentId,
      stripeCustomerId: customerId,
      stripeSubscriptionId: subscription.id,
      stripePriceId: firstItem?.price.id ?? null,
      status: subscription.status,
      currentPeriodEnd: periodEnd,
    })
    .onConflictDoUpdate({
      target: billingSubscriptions.stripeSubscriptionId,
      set: {
        deploymentId,
        stripePriceId: firstItem?.price.id ?? null,
        status: subscription.status,
        currentPeriodEnd: periodEnd,
        updatedAt: new Date(),
      },
    });
}

export async function recordInferenceUsage(input: {
  idempotencyKey: string;
  userId: string;
  deploymentId: string;
  executionId?: string | null;
  eventId?: number | null;
  model?: string | null;
  inputTokens?: number;
  outputTokens?: number;
  cacheCreationInputTokens?: number;
  cacheReadInputTokens?: number;
  providerCostMicros?: number;
}) {
  const providerCostMicros = Math.max(0, Math.round(input.providerCostMicros ?? 0));
  const chargeAmountCents = chargeCentsForProviderCostMicros(providerCostMicros);
  const id = randomUUID();

  const [usage] = await db
    .insert(inferenceUsageEvents)
    .values({
      id,
      userId: input.userId,
      deploymentId: input.deploymentId,
      executionId: input.executionId ?? null,
      eventId: input.eventId ?? null,
      model: input.model ?? null,
      inputTokens: Math.max(0, Math.round(input.inputTokens ?? 0)),
      outputTokens: Math.max(0, Math.round(input.outputTokens ?? 0)),
      cacheCreationInputTokens: Math.max(0, Math.round(input.cacheCreationInputTokens ?? 0)),
      cacheReadInputTokens: Math.max(0, Math.round(input.cacheReadInputTokens ?? 0)),
      providerCostMicros,
      chargeAmountCents,
      idempotencyKey: input.idempotencyKey,
    })
    .onConflictDoNothing()
    .returning();

  if (!usage) {
    const [existing] = await db
      .select()
      .from(inferenceUsageEvents)
      .where(eq(inferenceUsageEvents.idempotencyKey, input.idempotencyKey))
      .limit(1);
    return { usage: existing, ledgerEntry: null, inserted: false };
  }

  const ledgerEntry =
    chargeAmountCents > 0
      ? await appendCreditLedgerEntry({
          userId: input.userId,
          deploymentId: input.deploymentId,
          source: "inference_usage",
          amountCents: -chargeAmountCents,
          description: input.model ? `Inference usage: ${input.model}` : "Inference usage",
        })
      : null;

  await db
    .insert(billingOutboxEvents)
    .values({
      id: randomUUID(),
      eventType: "stripe.meter_event.inference_usage",
      aggregateId: usage.id,
      payload: JSON.stringify({
        usage_event_id: usage.id,
        deployment_id: usage.deploymentId,
        user_id: usage.userId,
        model: usage.model,
        tokens:
          usage.inputTokens +
          usage.outputTokens +
          usage.cacheCreationInputTokens +
          usage.cacheReadInputTokens,
        charge_amount_cents: usage.chargeAmountCents,
      }),
    })
    .onConflictDoNothing();

  return { usage, ledgerEntry, inserted: true };
}

export async function processBillingOutbox(limit = 25) {
  if (!stripe) throw new Error("Stripe is not configured");
  const meterEventName =
    process.env.STRIPE_INFERENCE_METER_EVENT_NAME || "centaur_inference_usage";
  const rows = await db
    .select()
    .from(billingOutboxEvents)
    .where(eq(billingOutboxEvents.status, "pending"))
    .orderBy(billingOutboxEvents.createdAt)
    .limit(limit);

  let processed = 0;
  let failed = 0;
  for (const row of rows) {
    try {
      const payload = JSON.parse(row.payload) as {
        usage_event_id?: string;
        user_id?: string;
        tokens?: number;
      };
      if (!payload.user_id) throw new Error("outbox payload missing user_id");
      const [customer] = await db
        .select()
        .from(billingCustomers)
        .where(eq(billingCustomers.userId, payload.user_id))
        .limit(1);
      if (!customer) throw new Error("billing customer not found");

      const meterEvent = await stripe.billing.meterEvents.create(
        {
          event_name: meterEventName,
          identifier: row.id,
          payload: {
            stripe_customer_id: customer.stripeCustomerId,
            value: String(Math.max(0, Math.round(payload.tokens ?? 0))),
          },
        },
        { idempotencyKey: row.id }
      );

      await db
        .update(billingOutboxEvents)
        .set({ status: "processed", processedAt: new Date(), lastError: null })
        .where(eq(billingOutboxEvents.id, row.id));

      if (payload.usage_event_id) {
        await db
          .update(inferenceUsageEvents)
          .set({
            status: "reported",
            stripeMeterEventId: meterEvent.identifier,
            reportedAt: new Date(),
            errorMessage: null,
          })
          .where(eq(inferenceUsageEvents.id, payload.usage_event_id));
      }
      processed++;
    } catch (err) {
      failed++;
      const attempts = row.attempts + 1;
      await db
        .update(billingOutboxEvents)
        .set({
          attempts,
          status: attempts >= 10 ? "failed" : "pending",
          lastError: err instanceof Error ? err.message.slice(0, 500) : String(err),
        })
        .where(eq(billingOutboxEvents.id, row.id));
    }
  }

  return { processed, failed };
}

export async function recentCreditLedger(userId: string, limit = 10) {
  return db
    .select()
    .from(creditLedgerEntries)
    .where(eq(creditLedgerEntries.userId, userId))
    .orderBy(desc(creditLedgerEntries.createdAt))
    .limit(limit);
}

export async function activeSubscriptionForDeployment(deploymentId: string) {
  const [subscription] = await db
    .select()
    .from(billingSubscriptions)
    .where(and(
      eq(billingSubscriptions.deploymentId, deploymentId),
      eq(billingSubscriptions.status, "active")
    ))
    .limit(1);
  return subscription ?? null;
}
