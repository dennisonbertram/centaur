import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import { pgTable, text, timestamp, integer } from "drizzle-orm/pg-core";

const client = postgres(process.env.DATABASE_URL!);
export const db = drizzle(client);

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
  deploymentId: text("deployment_id").notNull(),
  name: text("name").notNull(),
  valueMasked: text("value_masked").notNull().default(""),
  pendingValue: text("pending_value"),
  isSet: integer("is_set").notNull().default(0),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export const usageEvents = pgTable("usage_events", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  deploymentId: text("deployment_id").notNull(),
  eventType: text("event_type").notNull(),
  count: integer("count").notNull().default(1),
  recordedAt: timestamp("recorded_at").defaultNow().notNull(),
});
