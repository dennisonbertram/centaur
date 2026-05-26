import assert from "node:assert/strict";
import test from "node:test";

import {
  canRevokeActiveKey,
  generateDeploymentApiKey,
  hashApiKey,
  keyPrefix,
} from "./api-keys.ts";

test("generates deployment-scoped API keys without storing plaintext metadata", () => {
  const key = generateDeploymentApiKey("demo-prod");

  assert.match(key, /^centaur-demo-prod-[a-f0-9]{32}$/);
  assert.equal(keyPrefix(key), key.slice(0, 12));
});

test("hashes API keys with SHA-256", () => {
  const key = "centaur-demo-prod-0123456789abcdef0123456789abcdef";
  const hash = hashApiKey(key);

  assert.match(hash, /^[a-f0-9]{64}$/);
  assert.notEqual(hash, key);
  assert.equal(hash, hashApiKey(key));
});

test("prevents revoking the last active API key", () => {
  assert.equal(canRevokeActiveKey(1), false);
  assert.equal(canRevokeActiveKey(2), true);
});
