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

export interface WorkingCapitalRow {
  case_id: string
  plan_variant: PlanVariant
  period: string
  business_unit: string
  revenue: number | null
  cogs: number | null
  ar_days: number | null
  inventory_days: number | null
  ap_days: number | null
  ar_balance: number | null
  inventory_balance: number | null
  ap_balance: number | null
  nwc: number | null
  ccc: number | null
  provenance: string
}

export interface WorkingCapitalInputRow {
  case_id: string
  plan_variant: PlanVariant
  period: string
  business_unit: string
  ar_days: number | null
  inventory_days: number | null
  ap_days: number | null
  provenance: string
}

export interface WorkingCapitalPlan {
  rows: WorkingCapitalRow[]
  provenance?: string
}

export interface CashAssumptionRow {
  case_id: string
  plan_variant: PlanVariant
  period: string
  opening_cash: number | null
  minimum_cash_buffer: number | null
  capex: number | null
  other_cash_items: number | null
  provenance: string
}

export interface CashBridgeRow extends CashAssumptionRow {
  operating_profit: number | null
  prior_ar: number | null
  current_ar: number | null
  prior_inventory: number | null
  current_inventory: number | null
  prior_ap: number | null
  current_ap: number | null
  net_cash_change: number | null
  closing_illustrative_cash: number | null
  headroom: number | null
  status: string
}

export interface CashBridge {
  rows: CashBridgeRow[]
  closing_illustrative_cash: number | null
  minimum_headroom: number | null
  disclosure: string
}

export interface ForecastAccuracy {
  wape: number | null
  bias: number | null
  directional_hit_rate: number | null
  eligible_periods: number
  status: string
  provenance: string
}

export interface ActionRegisterRow {
  action_id: string
  observation: string
  driver: string
  impact: number | null
  risk: string
  action: string
  owner: string
  due_period: string
  cadence: string
  status?: string
  provenance: string
}

export interface ScenarioDecisionRow {
  plan_variant: PlanVariant
  fy_revenue_delta: number | null
  fy_operating_profit_delta: number | null
  minimum_cash_month: string | null
  cash_headroom: number | null
  ccc: number | null
  top_revenue_driver: string | null
  top_profit_driver: string | null
  top_cash_driver: string | null
  owner: string | null
  next_review_date: string | null
  provenance: string
}

export interface CashBridgeReconciliationEvidence {
  status: string
  max_residual: number | null
}

export interface CategoryRollupReconciliationEvidence {
  status: string
  revenue_residual: number | null
}

export interface ReconciliationStatus {
  status: string
  tolerance_rmb_millions: number
  cash_bridge: CashBridgeReconciliationEvidence
  category_rollup: CategoryRollupReconciliationEvidence
}

export type WorkforceRoleGroup = 'store operations' | 'commercial' | 'supply chain' | 'finance/support'

export interface WorkforceCapacityRow {
  case_id: string
  plan_variant: PlanVariant
  period: string
  business_unit: string
  role_group: WorkforceRoleGroup
  planned_fte: number
  required_fte: number
  monthly_loaded_cost: number
  loaded_cost: number
  revenue: number
  revenue_per_fte: number | null
  capacity_gap: number
  productivity_basis: string
  status: string
  provenance: string
  input_provenance?: string
}

export interface WorkforceCapacityRollup {
  planned_fte: number
  required_fte: number
  loaded_cost: number
  capacity_gap: number
  revenue?: number
  revenue_per_fte?: number | null
  row_count: number
  provenance: string
  variant_delta?: number
}

export interface WorkforceReconciliationEvidence {
  status: string
  tolerance_rmb_millions?: number | null
  residual?: number | null
  max_residual?: number | null
  no_double_counting?: boolean
  portfolio_equals_business_units?: boolean
  business_units_equal_role_groups?: boolean
  [key: string]: unknown
}

export interface WorkforceCapacityResponse {
  case_id: string
  as_of_date: string
  currency: string
  unit: string
  plan_variant: PlanVariant
  headcount_rows: WorkforceCapacityRow[]
  locked_rows: Array<Record<string, unknown>>
  rollups: {
    role_group: Record<WorkforceRoleGroup, WorkforceCapacityRollup>
    business_unit: Record<string, WorkforceCapacityRollup>
    role_group_business_unit: Record<WorkforceRoleGroup, Record<string, WorkforceCapacityRollup>>
    portfolio: WorkforceCapacityRollup
  }
  selected_vs_base_delta: Record<string, number>
  reconciliation_evidence: WorkforceReconciliationEvidence
  provenance: string
  input_provenance: string
  disclosure: string
}

export interface WorkforceCapacityInputRow {
  case_id: string
  plan_variant: PlanVariant
  period: string
  business_unit: string
  role_group: WorkforceRoleGroup
  planned_fte: number
  monthly_loaded_cost: number
  provenance: 'synthetic_plan'
}

export interface OperatingPlanResponse {
  as_of_date: string
  planning_horizon: PlanningHorizon
  plan_variant: PlanVariant
  provenance_legend: Record<string, string>
  working_capital: WorkingCapitalPlan
  cash_bridge: CashBridge
  forecast_accuracy: ForecastAccuracy
  actions: ActionRegisterRow[]
  decision_table: ScenarioDecisionRow[]
  reconciliation: ReconciliationStatus
  headcount_rows?: WorkforceCapacityRow[]
  workforce_capacity?: WorkforceCapacityResponse
  headcount_capacity?: WorkforceCapacityResponse
}

export interface OperatingPlanPreviewRequest {
  case_id: string
  selected_plan_variant: PlanVariant
  planning_input_source: PlanningInputSource
  rows: PlanningInputRow[]
  working_capital_rows: WorkingCapitalInputRow[]
  cash_assumption_rows: CashAssumptionRow[]
  headcount_rows?: WorkforceCapacityInputRow[]
  actions?: Array<{
    case_id: string
    observation: string
    driver: string
    impact: number | null
    risk: string
    action: string
    owner: string
    due_period: string
    cadence: string
    provenance: string
  }>
}
