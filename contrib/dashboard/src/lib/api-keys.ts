import { createHash, randomBytes } from "crypto";

export const API_KEY_PREFIX_LENGTH = 12;
export const DEFAULT_API_KEY_NAME = "Default";

export function generateDeploymentApiKey(deploymentId: string): string {
  return `centaur-${deploymentId}-${randomBytes(16).toString("hex")}`;
}

export function hashApiKey(key: string): string {
  return createHash("sha256").update(key).digest("hex");
}

export function keyPrefix(key: string): string {
  return key.slice(0, API_KEY_PREFIX_LENGTH);
}

export function canRevokeActiveKey(activeKeyCount: number): boolean {
  return activeKeyCount > 1;
}

export function normalizeApiKeyName(name: unknown): string {
  if (typeof name !== "string") return DEFAULT_API_KEY_NAME;
  const trimmed = name.trim();
  return trimmed || DEFAULT_API_KEY_NAME;
}

export function maskApiKeyValue(key: string): string {
  if (key.length <= 10) return "set";
  return `${key.slice(0, 6)}...${key.slice(-4)}`;
}
