export type CellFormat = "currency" | "percent" | "number" | "date" | "text";

export type ColumnDef = {
  key: string;
  label: string;
  format: CellFormat;
  sortable?: boolean;
};

export type DataTableProps = {
  type: "data-table";
  columns: ColumnDef[];
  data: Record<string, unknown>[];
  defaultSort?: { key: string; direction: "asc" | "desc" };
  searchable?: boolean;
  title?: string;
};

export type KPICardProps = {
  type: "kpi-card";
  label: string;
  value: number;
  format: CellFormat;
  delta?: number;
};

export type LineChartProps = {
  type: "line-chart";
  title: string;
  xKey: string;
  yKeys: string[];
  data: Record<string, unknown>[];
  xFormat?: CellFormat;
  yFormat?: CellFormat;
};

export type BarChartProps = {
  type: "bar-chart";
  title: string;
  categoryKey: string;
  valueKey: string;
  data: Record<string, unknown>[];
};

export type PieChartProps = {
  type: "pie-chart";
  title: string;
  labelKey: string;
  valueKey: string;
  data: Record<string, unknown>[];
};

export type DashboardComponent =
  | DataTableProps
  | KPICardProps
  | LineChartProps
  | BarChartProps
  | PieChartProps;

export type DashboardSpec = {
  title: string;
  layout: "single" | "grid-2" | "grid-3";
  components: DashboardComponent[];
};

// DataSource types (subset from components/dashboard/types for bot usage)
export type InlineDataSource = { type: "inline" };
export type SqlDataSource = { type: "sql"; query: string; refreshInterval?: number; target?: string };
export type ApiDataSource = { type: "api"; endpoint: string; params?: Record<string, string>; refreshInterval?: number };
export type DataSource = InlineDataSource | SqlDataSource | ApiDataSource;
