import assert from "node:assert/strict";
import test from "node:test";

import { chargeCentsForProviderCostMicros, dollarsToMicros } from "./billing-pricing.ts";

test("converts provider dollars to integer micros", () => {
  assert.equal(dollarsToMicros(0), 0);
  assert.equal(dollarsToMicros(0.012345), 12345);
});

test("charges at least one cent for nonzero managed inference usage", () => {
  delete process.env.INFERENCE_MARKUP_BASIS_POINTS;

  assert.equal(chargeCentsForProviderCostMicros(0), 0);
  assert.equal(chargeCentsForProviderCostMicros(1), 1);
  assert.equal(chargeCentsForProviderCostMicros(1_000_000), 120);
});
