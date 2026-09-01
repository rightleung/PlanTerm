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
  gross_margin_actual: number | null
  gross_margin_budget: number | null
  operating_expense_actual: number | null
  operating_expense_budget: number | null
  operating_profit_variance: number | null
  forecast_gap: number | null
  fy_budget: number | null
  fy_forecast: number | null
  price_amount: number | null
  volume_amount: number | null
  mix_amount: number | null
  primary_driver: string | null
  profit_driver: string | null
  profit_driver_amount: number | null
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
  revenue_driver: string | null
  profit_driver: string | null
  profit_driver_amount: number | null
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
    profit_allocation_indices: Record<string, { gross_margin_index: number; operating_margin_index: number }>
    h2_forecast_adjustment_vs_budget: Record<string, number>
    monthly_seasonality: Record<string, number>
    actual_ticket_factors_vs_budget: Record<string, number>
    note: string
  }
  available_filters: { brands: BrandFilter[]; markets: MarketFilter[]; business_units: string[]; valid_combinations: { brand: Exclude<BrandFilter, 'all'>; market: Exclude<MarketFilter, 'all'>; business_unit: string }[] }
  selected_filters: { brand: BrandFilter; market: MarketFilter }
  kpis: KpiSnapshot[]
  monthly_trend: MonthlyTrendPoint[]
  business_unit_variances: VarianceRow[]
  pvm_bridge: PvmBridge
  management_insights: ManagementInsight[]
  data_sources: DataSource[]
  provenance_legend: Record<string, string>
  selected_plan_variant?: PlanVariant
  planning_input_source?: PlanningInputSource
  planning_horizon?: PlanningHorizon
  category_detail?: CategoryDetail[]
  category_detail_context?: CategoryDetailContext[]
  scenario_comparison?: ScenarioComparison
  category_taxonomy_disclosure?: CategoryTaxonomyDisclosure
}

export type PlanVariant = 'base' | 'upside' | 'downside'
export type PlanningInputSource = 'seed' | 'upload' | 'editor'
export interface PlanningHorizon { locked_through: string; editable_from: string; editable_to: string }
export interface PlanningInputRow {
  case_id: string
  plan_variant: PlanVariant
  period: string
  business_unit: string
  category_id: string
  volume_change_pct: number
  average_ticket_change_pct: number
  gross_margin_delta_pp: number
  opex_ratio_delta_pp: number
  category_name?: string
  brand?: string
  market?: string
  provenance?: string
}
export interface CategoryDetail {
  period: string; plan_variant: PlanVariant; business_unit: string; category_id: string; category_name: string
  revenue: number; revenue_mix_pct: number; gross_margin_pct: number; opex_ratio_pct: number; operating_margin_pct: number; provenance: string
}
export interface CategoryFinancialContext {
  revenue: number; volume: number; average_ticket: number | null; gross_profit: number; cost_of_sales: number; operating_expense: number; operating_profit: number
  gross_margin_pct: number | null; opex_ratio_pct: number | null; operating_margin_pct: number | null
}
export interface CategoryDetailContext {
  business_unit: string; category_id: string; category_name: string
  provenance: 'synthetic_allocation'; allocation_basis: 'committed_category_revenue_share'
  h1_actual: CategoryFinancialContext; h1_prior_year: CategoryFinancialContext; fy_budget: CategoryFinancialContext
}
export interface ScenarioMetric { base_fy_forecast: number; selected_fy_forecast: number; delta: number; unit: string }
export interface ScenarioComparison { selected_plan_variant: PlanVariant; revenue: ScenarioMetric; gross_profit: ScenarioMetric; operating_profit: ScenarioMetric }
export interface CategoryTaxonomyDisclosure {
  disclosure: string
  taxonomy_provenance: string
  official_taxonomy_note: string
  official_source: { source_url: string; source_period: string; publisher: string; document_title: string }
  official_label_registry: Array<{ source_label: string; brand: string; source_url: string; source_period: string; planning_category_id: string }>
  categories: Array<{ category_id: string; category_name: string; brand: string; market: string; business_unit: string; provenance: string }>
}
