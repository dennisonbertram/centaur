import { NextResponse } from "next/server";
import { processBillingOutbox } from "@/lib/billing";

export async function POST(request: Request) {
  const expectedSecret = process.env.CENTAUR_BILLING_EVENTS_SECRET;
  const providedSecret = request.headers.get("x-centaur-billing-secret");
  if (!expectedSecret || providedSecret !== expectedSecret) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json().catch(() => ({}));
  const limit = Math.min(100, Math.max(1, Number(body.limit ?? 25)));
  const result = await processBillingOutbox(limit);
  return NextResponse.json({ ok: true, ...result });
}
