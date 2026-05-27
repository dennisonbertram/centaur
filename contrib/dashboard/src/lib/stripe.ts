import Stripe from "stripe";

function getStripe(): Stripe | null {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) return null;
  return new Stripe(key, { apiVersion: "2026-04-22.dahlia" });
}

export const stripe = getStripe();

export const TIER_PRICES: Record<string, { priceId: string; amount: number }> = {
  dev: {
    priceId: process.env.STRIPE_PRICE_DEV || "price_dev_placeholder",
    amount: 900,
  },
  small: {
    priceId: process.env.STRIPE_PRICE_SMALL || "price_small_placeholder",
    amount: 8200,
  },
  prod: {
    priceId: process.env.STRIPE_PRICE_PROD || "price_prod_placeholder",
    amount: 13600,
  },
};

export const CREDIT_PACKS: Record<string, { label: string; amountCents: number }> = {
  starter: { label: "$25 inference credits", amountCents: 2500 },
  growth: { label: "$100 inference credits", amountCents: 10000 },
  scale: { label: "$500 inference credits", amountCents: 50000 },
};
