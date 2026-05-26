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
