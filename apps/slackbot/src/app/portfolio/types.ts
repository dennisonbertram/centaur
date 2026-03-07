export interface Position {
  assetName: string;
  ticker: string | null;
  fundName: string;
  fundShort: string;
  assetType: string; // "Token" | "Public" | "Private" | "Other"
  marketValue: number;
  grossInvestedCapital: number;
  moic: number;
  holding: number;
  realizedGainLoss: number;
  latestPrice: number | null;
}

/** Aggregated position: same asset across funds, with per-fund sub-rows. */
export interface AggregatedPosition {
  assetName: string;
  ticker: string | null;
  assetType: string;
  marketValue: number;
  grossInvestedCapital: number;
  moic: number;
  latestPrice: number | null;
  funds: Position[]; // per-fund breakdown
}
