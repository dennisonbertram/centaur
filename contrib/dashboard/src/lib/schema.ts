import { pgTable, text, timestamp, integer, unique } from "drizzle-orm/pg-core";

export const deployments = pgTable("deployments", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  name: text("name").notNull(),
  slug: text("slug").notNull().default(""),
  tier: text("tier").notNull().default("dev"),
  location: text("location").notNull().default("nbg1"),
  status: text("status").notNull().default("provisioning"),
  ip: text("ip"),
  loadBalancerIp: text("load_balancer_ip"),
  kubeconfigPath: text("kubeconfig_path"),
  apiKey: text("api_key"),
  monthlyCost: text("monthly_cost"),
  inferenceMode: text("inference_mode").notNull().default("byok"),
  errorMessage: text("error_message"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export const credentials = pgTable("credentials", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  deploymentId: text("deployment_id")
    .notNull()
    .references(() => deployments.id, { onDelete: "cascade" }),
  name: text("name").notNull(),
  valueMasked: text("value_masked").notNull().default(""),
  pendingValue: text("pending_value"),
  isSet: integer("is_set").notNull().default(0),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
}, (t) => [
  unique().on(t.deploymentId, t.name),
]);

export const apiKeys = pgTable("api_keys", {
  id: text("id").primaryKey(),
  deploymentId: text("deployment_id")
    .notNull()
    .references(() => deployments.id, { onDelete: "cascade" }),
  keyPrefix: text("key_prefix").notNull(),
  keyHash: text("key_hash").notNull(),
  name: text("name").notNull().default("Default"),
  pendingValue: text("pending_value"),
  revealValue: text("reveal_value"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  lastUsedAt: timestamp("last_used_at"),
  revokedAt: timestamp("revoked_at"),
  revocationPushedAt: timestamp("revocation_pushed_at"),
}, (t) => [
  unique().on(t.keyHash),
]);

export const usageEvents = pgTable("usage_events", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  deploymentId: text("deployment_id")
    .notNull()
    .references(() => deployments.id, { onDelete: "cascade" }),
  eventType: text("event_type").notNull(),
  count: integer("count").notNull().default(1),
  recordedAt: timestamp("recorded_at").defaultNow().notNull(),
});

export const billingCustomers = pgTable("billing_customers", {
  userId: text("user_id").primaryKey(),
  stripeCustomerId: text("stripe_customer_id").notNull(),
  email: text("email"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
}, (t) => [
  unique().on(t.stripeCustomerId),
]);

export const billingSubscriptions = pgTable("billing_subscriptions", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  deploymentId: text("deployment_id").references(() => deployments.id, { onDelete: "set null" }),
  stripeCustomerId: text("stripe_customer_id").notNull(),
  stripeSubscriptionId: text("stripe_subscription_id").notNull(),
  stripePriceId: text("stripe_price_id"),
  status: text("status").notNull(),
  currentPeriodEnd: timestamp("current_period_end"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
}, (t) => [
  unique().on(t.stripeSubscriptionId),
]);

export const creditLedgerEntries = pgTable("credit_ledger_entries", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  deploymentId: text("deployment_id").references(() => deployments.id, { onDelete: "set null" }),
  stripeCustomerId: text("stripe_customer_id"),
  stripeEventId: text("stripe_event_id"),
  source: text("source").notNull(),
  amountCents: integer("amount_cents").notNull(),
  balanceAfterCents: integer("balance_after_cents").notNull(),
  description: text("description"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
}, (t) => [
  unique().on(t.stripeEventId, t.source),
]);

export const inferenceUsageEvents = pgTable("inference_usage_events", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  deploymentId: text("deployment_id").notNull().references(() => deployments.id, { onDelete: "cascade" }),
  executionId: text("execution_id"),
  eventId: integer("event_id"),
  model: text("model"),
  inputTokens: integer("input_tokens").notNull().default(0),
  outputTokens: integer("output_tokens").notNull().default(0),
  cacheCreationInputTokens: integer("cache_creation_input_tokens").notNull().default(0),
  cacheReadInputTokens: integer("cache_read_input_tokens").notNull().default(0),
  providerCostMicros: integer("provider_cost_micros").notNull().default(0),
  chargeAmountCents: integer("charge_amount_cents").notNull().default(0),
  idempotencyKey: text("idempotency_key").notNull(),
  stripeMeterEventId: text("stripe_meter_event_id"),
  status: text("status").notNull().default("pending"),
  errorMessage: text("error_message"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  reportedAt: timestamp("reported_at"),
}, (t) => [
  unique().on(t.idempotencyKey),
]);

export const billingOutboxEvents = pgTable("billing_outbox_events", {
  id: text("id").primaryKey(),
  eventType: text("event_type").notNull(),
  aggregateId: text("aggregate_id").notNull(),
  payload: text("payload").notNull(),
  status: text("status").notNull().default("pending"),
  attempts: integer("attempts").notNull().default(0),
  lastError: text("last_error"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  processedAt: timestamp("processed_at"),
}, (t) => [
  unique().on(t.eventType, t.aggregateId),
]);

export const stripeWebhookEvents = pgTable("stripe_webhook_events", {
  id: text("id").primaryKey(),
  eventType: text("event_type").notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});
