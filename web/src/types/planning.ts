export type BrandFilter = 'all' | 'MINISO' | 'TOP_TOY'
export type MarketFilter = 'all' | 'mainland' | 'overseas' | 'global'
export type Status = 'Favorable' | 'Unfavorable' | 'Neutral'

export interface KpiSnapshot {
  metric: string
  label: string
  unit: string
  actual_ytd: number | null
  budget_ytd: number | null
  variance_amount: number | null
  variance_pct: number | null
  prior_year_ytd: number | null
  yoy_pct: number | null
  fy_budget: number | null
  fy_forecast: number | null
  forecast_gap: number | null
  status: Status | null
}

export interface MonthlyTrendPoint {
  period: string
  actual: number | null
  budget: number | null
  forecast: number | null
  prior_year: number | null
}

export interface VarianceRow {
  business_unit: string
  brand: string
  market: string
  revenue_actual: number | null
  revenue_budget: number | null
  revenue_variance: number | null
  revenue_variance_pct: number | null
  gross_profit_actual: number | null
  gross_profit_budget: number | null
  operating_profit_actual: number | null
  operating_profit_budget: number | null
  operating_margin_actual: number | null
  operating_margin_budget: number | null
  operating_expense_actual: number | null
  operating_expense_budget: number | null
  forecast_gap: number | null
  price_amount: number | null
  volume_amount: number | null
  mix_amount: number | null
  primary_driver: string | null
  status: Status | null
}

export interface PvmBridge {
  actual_revenue: number | null
  budget_revenue: number | null
  volume: number | null
  mix: number | null
  price: number | null
  reconciliation_difference: number | null
  unit: string
}

export interface ManagementInsight {
  title: string
  business_unit: string
  severity: 'watch' | 'positive'
  message: string
  driver: string
  driver_amount: number | null
  forecast_gap: number | null
  action: string
}

export interface DataSource {
  name: string
  url: string
  source_date: string
  scope: string
}

export interface DashboardResponse {
  metadata: {
    case_id: string
    name: string
    description: string
    planning_year: string
    as_of_date: string
    currency: string
    unit: string
    accounting_standard: string
    business_units: string[]
  }
  assumptions: {
    budget_assumptions: Record<string, { revenue_growth_vs_fy2025: number; budget_gross_margin: number; budget_operating_margin: number; average_ticket: number }>
    h2_forecast_adjustment_vs_budget: Record<string, number>
    monthly_seasonality: Record<string, number>
    actual_ticket_factors_vs_budget: Record<string, number>
    note: string
  }
  available_filters: { brands: BrandFilter[]; markets: MarketFilter[]; business_units: string[] }
  selected_filters: { brand: BrandFilter; market: MarketFilter }
  kpis: KpiSnapshot[]
  monthly_trend: MonthlyTrendPoint[]
  business_unit_variances: VarianceRow[]
  pvm_bridge: PvmBridge
  management_insights: ManagementInsight[]
  data_sources: DataSource[]
  provenance_legend: Record<string, string>
}
