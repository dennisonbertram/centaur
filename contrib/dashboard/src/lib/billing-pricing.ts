const DEFAULT_MARKUP_BASIS_POINTS = 12000;

export function usageMarkupBasisPoints(): number {
  const raw = process.env.INFERENCE_MARKUP_BASIS_POINTS;
  if (!raw) return DEFAULT_MARKUP_BASIS_POINTS;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_MARKUP_BASIS_POINTS;
}

export function dollarsToMicros(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.round(value * 1_000_000);
}

export function chargeCentsForProviderCostMicros(providerCostMicros: number): number {
  if (!Number.isFinite(providerCostMicros) || providerCostMicros <= 0) return 0;
  const markedUpMicros = Math.ceil((providerCostMicros * usageMarkupBasisPoints()) / 10_000);
  return Math.max(1, Math.ceil(markedUpMicros / 10_000));
}
