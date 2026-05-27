ALTER TABLE deployments
  ADD COLUMN IF NOT EXISTS inference_mode text NOT NULL DEFAULT 'byok';

CREATE TABLE IF NOT EXISTS billing_customers (
  user_id text PRIMARY KEY,
  stripe_customer_id text NOT NULL UNIQUE,
  email text,
  created_at timestamp NOT NULL DEFAULT now(),
  updated_at timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS billing_subscriptions (
  id text PRIMARY KEY,
  user_id text NOT NULL,
  deployment_id text REFERENCES deployments(id) ON DELETE SET NULL,
  stripe_customer_id text NOT NULL,
  stripe_subscription_id text NOT NULL UNIQUE,
  stripe_price_id text,
  status text NOT NULL,
  current_period_end timestamp,
  created_at timestamp NOT NULL DEFAULT now(),
  updated_at timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS credit_ledger_entries (
  id text PRIMARY KEY,
  user_id text NOT NULL,
  deployment_id text REFERENCES deployments(id) ON DELETE SET NULL,
  stripe_customer_id text,
  stripe_event_id text,
  source text NOT NULL,
  amount_cents integer NOT NULL,
  balance_after_cents integer NOT NULL,
  description text,
  created_at timestamp NOT NULL DEFAULT now(),
  UNIQUE (stripe_event_id, source)
);

CREATE TABLE IF NOT EXISTS inference_usage_events (
  id text PRIMARY KEY,
  user_id text NOT NULL,
  deployment_id text NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
  execution_id text,
  event_id integer,
  model text,
  input_tokens integer NOT NULL DEFAULT 0,
  output_tokens integer NOT NULL DEFAULT 0,
  cache_creation_input_tokens integer NOT NULL DEFAULT 0,
  cache_read_input_tokens integer NOT NULL DEFAULT 0,
  provider_cost_micros integer NOT NULL DEFAULT 0,
  charge_amount_cents integer NOT NULL DEFAULT 0,
  idempotency_key text NOT NULL UNIQUE,
  stripe_meter_event_id text,
  status text NOT NULL DEFAULT 'pending',
  error_message text,
  created_at timestamp NOT NULL DEFAULT now(),
  reported_at timestamp
);

CREATE INDEX IF NOT EXISTS inference_usage_events_deployment_idx
  ON inference_usage_events (deployment_id, created_at DESC);

CREATE TABLE IF NOT EXISTS billing_outbox_events (
  id text PRIMARY KEY,
  event_type text NOT NULL,
  aggregate_id text NOT NULL,
  payload text NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  attempts integer NOT NULL DEFAULT 0,
  last_error text,
  created_at timestamp NOT NULL DEFAULT now(),
  processed_at timestamp,
  UNIQUE (event_type, aggregate_id)
);

CREATE INDEX IF NOT EXISTS billing_outbox_events_pending_idx
  ON billing_outbox_events (status, created_at);

CREATE TABLE IF NOT EXISTS stripe_webhook_events (
  id text PRIMARY KEY,
  event_type text NOT NULL,
  created_at timestamp NOT NULL DEFAULT now()
);
