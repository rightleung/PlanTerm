import { useEffect, useRef, useState } from 'react'
import { fetchDashboard, fetchForecastAccuracy, fetchOperatingPlan, fetchPlanningTemplate, previewDashboard, previewOperatingPlan, ApiError } from '@/api/client'
import { exportManagementPack } from '@/export/managementPack'
import { DataProvenance } from '@/features/dashboard/DataProvenance'
import { FilterBar } from '@/features/dashboard/FilterBar'
import { KpiGrid } from '@/features/dashboard/KpiGrid'
import { ManagementInsights } from '@/features/dashboard/ManagementInsights'
import { MonthlyTrendChart } from '@/features/dashboard/MonthlyTrendChart'
import { PvmBridge } from '@/features/dashboard/PvmBridge'
import { VarianceTable } from '@/features/dashboard/VarianceTable'
import { parsePlanningInputCsv, PlanningInputs, type PlanningSession } from '@/features/planning-inputs/PlanningInputs'
import { ActionRegister } from '@/features/operating-plan/ActionRegister'
import { CashBridge } from '@/features/operating-plan/CashBridge'
import { ForecastAccuracy } from '@/features/operating-plan/ForecastAccuracy'
import { ScenarioDecisionTable } from '@/features/operating-plan/ScenarioDecisionTable'
import type { ActionRegisterRow, BrandFilter, DashboardResponse, MarketFilter, OperatingPlanResponse } from '@/types/planning'

const CASE_ID = 'miniso-2026'

function sessionActionRows(actions: ActionRegisterRow[]) {
  return actions.map((action, index) => ({ ...action, action_id: action.action_id || `seed-${index}`, status: action.status || 'Open', due_period: action.due_period || '' }))
}

function operatingActionPayload(action: ActionRegisterRow) {
  return { case_id: CASE_ID, observation: action.observation, driver: action.driver, impact: action.impact, risk: action.risk, action: action.action, owner: action.owner, due_period: action.due_period, cadence: action.cadence, provenance: action.provenance }
}

export default function App() {
  const [brand, setBrand] = useState<BrandFilter>('all')
  const [market, setMarket] = useState<MarketFilter>('all')
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [exporting, setExporting] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [planningSession, setPlanningSession] = useState<PlanningSession | null>(null)
  const [sessionRevision, setSessionRevision] = useState(0)
  const [operatingPlan, setOperatingPlan] = useState<OperatingPlanResponse | null>(null)
  const [operatingLoading, setOperatingLoading] = useState(true)
  const [operatingError, setOperatingError] = useState<ApiError | Error | null>(null)
  const [operatingRetryCount, setOperatingRetryCount] = useState(0)
  const [sessionActions, setSessionActions] = useState<ActionRegisterRow[]>([])
  const requestId = useRef(0)
  const dashboardController = useRef<AbortController | null>(null)
  const operatingRequestId = useRef(0)
  const operatingController = useRef<AbortController | null>(null)
  const planningSessionRef = useRef<PlanningSession | null>(null)
  const operatingPlanRef = useRef<OperatingPlanResponse | null>(null)
  const sessionActionsRef = useRef<ActionRegisterRow[]>([])
  planningSessionRef.current = planningSession
  operatingPlanRef.current = operatingPlan
  sessionActionsRef.current = sessionActions

  const marketIsAllowed = (nextBrand: BrandFilter, nextMarket: MarketFilter) => {
    if (nextMarket === 'all' || !dashboard) return true
    return dashboard.available_filters.valid_combinations.some((combination) => (nextBrand === 'all' || combination.brand === nextBrand) && combination.market === nextMarket)
  }

  const handleBrandChange = (nextBrand: BrandFilter) => {
    setBrand(nextBrand)
    if (!marketIsAllowed(nextBrand, market)) setMarket('all')
  }

  useEffect(() => {
    let active = true
    const id = ++requestId.current
    const controller = new AbortController()
    dashboardController.current = controller
    setLoading(true)
    setError(null)
    const activeSession = planningSessionRef.current
    const load = activeSession
      ? previewDashboard(CASE_ID, activeSession.rows, activeSession.variant, activeSession.source, brand, market, controller.signal)
      : fetchDashboard(CASE_ID, brand, market, controller.signal)
    load.then((result) => {
      if (active && id === requestId.current) setDashboard(result)
    }).catch((reason: unknown) => {
      if (active && id === requestId.current && (reason as Error).name !== 'AbortError') setError(reason instanceof Error ? reason : new Error('Unable to load dashboard'))
    }).finally(() => { if (active && id === requestId.current) setLoading(false) })
    return () => {
      active = false
      controller.abort()
      if (dashboardController.current === controller) dashboardController.current = null
    }
  }, [brand, market, retryCount, sessionRevision])

  useEffect(() => {
    let active = true
    const id = ++operatingRequestId.current
    const controller = new AbortController()
    operatingController.current?.abort()
    operatingController.current = controller
    setOperatingLoading(true)
    setOperatingError(null)
    const currentSession = planningSessionRef.current
    const currentPlan = operatingPlanRef.current
    const load = (async () => {
      if (!currentSession) return fetchOperatingPlan(CASE_ID, 'base', controller.signal)

      // Operating assumptions are variant-scoped. If the dashboard selection
      // changes before the prior plan state has caught up, seed the selected
      // variant before constructing the preview request.
      const selectedPlan = currentPlan?.plan_variant === currentSession.variant
        ? currentPlan
        : await fetchOperatingPlan(CASE_ID, currentSession.variant, controller.signal)
      const workingCapitalRows = selectedPlan.working_capital.rows
        .filter((row) => row.plan_variant === currentSession.variant)
        .map((row) => ({ case_id: row.case_id, plan_variant: currentSession.variant, period: row.period, business_unit: row.business_unit, ar_days: row.ar_days, inventory_days: row.inventory_days, ap_days: row.ap_days, provenance: 'synthetic_plan' as const }))
      const cashAssumptionRows = selectedPlan.cash_bridge.rows
        .filter((row) => row.plan_variant === currentSession.variant)
        .map((row) => ({ case_id: row.case_id, plan_variant: currentSession.variant, period: row.period, opening_cash: row.opening_cash, minimum_cash_buffer: row.minimum_cash_buffer, capex: row.capex, other_cash_items: row.other_cash_items, provenance: 'synthetic_plan' as const }))
      return previewOperatingPlan(CASE_ID, {
        case_id: CASE_ID,
        selected_plan_variant: currentSession.variant,
        planning_input_source: currentSession.source,
        rows: currentSession.rows,
        working_capital_rows: workingCapitalRows,
        cash_assumption_rows: cashAssumptionRows,
        actions: sessionActionsRef.current.map(operatingActionPayload),
      }, controller.signal)
    })()
    load.then(async (result) => {
      if (!active || id !== operatingRequestId.current) return
      const accuracy = await fetchForecastAccuracy(CASE_ID, controller.signal).catch(() => null)
      if (active && id === operatingRequestId.current) {
        setOperatingPlan(accuracy ? { ...result, forecast_accuracy: accuracy } : result)
        setSessionActions((current) => current.length > 0 ? current : sessionActionRows(result.actions))
      }
    }).catch((reason: unknown) => {
      if (active && id === operatingRequestId.current && (reason as Error).name !== 'AbortError') setOperatingError(reason instanceof Error ? reason : new Error('Unable to load operating decision plan'))
    }).finally(() => { if (active && id === operatingRequestId.current) setOperatingLoading(false) })
    return () => {
      active = false
      controller.abort()
      if (operatingController.current === controller) operatingController.current = null
    }
  }, [operatingRetryCount, sessionRevision])

  const applyPreview = (next: DashboardResponse, nextSession: PlanningSession) => {
    // A preview is browser-session state, while dashboard GET reads committed
    // seed data. Invalidate and cancel any in-flight seed request before using
    // the preview so an older GET cannot replace the selected scenario.
    requestId.current += 1
    dashboardController.current?.abort()
    dashboardController.current = null
    setPlanningSession(nextSession)
    setSessionRevision((revision) => revision + 1)
    setDashboard(next)
    setError(null)
    setLoading(false)
  }

  const discardAll = () => {
    requestId.current += 1
    dashboardController.current?.abort()
    dashboardController.current = null
    setPlanningSession(null)
    setSessionRevision((revision) => revision + 1)
    setError(null)
  }

  const resetFilters = () => { setBrand('all'); setMarket('all') }

  const download = async () => {
    if (!dashboard || dashboard.business_unit_variances.length === 0) return
    setExporting(true)
    try { const rows = planningSession?.rows || parsePlanningInputCsv(await fetchPlanningTemplate(CASE_ID)); await exportManagementPack(dashboard, rows, operatingPlan, sessionActions) } catch (reason: unknown) { setError(reason instanceof Error ? reason : new Error('Excel export failed')) } finally { setExporting(false) }
  }
  const selectedCategoryDetail = dashboard?.category_detail?.filter((row) => row.plan_variant === (dashboard.selected_plan_variant || 'base')) || []

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand-lockup"><div className="brand-mark">PT</div><div><div className="brand-name">PlanTerm</div><div className="brand-subtitle">FP&amp;A planning workbench</div></div></div>
        <div className="header-meta"><span className="status-dot" />Local case · no live data dependency</div>
      </header>

      <div className="content">
        <section className="hero">
          <div><div className="eyebrow">MINISO Group · Management view</div><h1>Portfolio planning &amp; performance</h1><p className="hero-copy">A disciplined view of Actual, Budget, Forecast and Prior Year across the three-business-unit MINISO case.</p></div>
          <div className="hero-side"><span className="case-label">{dashboard?.metadata.name || 'MINISO FP&A Portfolio MVP'}</span><strong>As of {dashboard?.metadata.as_of_date || '2026-06-30'}</strong><span>RMB millions · IFRS basis</span></div>
        </section>

        <div className="callout"><span className="callout-icon">i</span><span>Public reported data anchors H1 Actual and Prior Year. Budget, Forecast, monthly allocations and business-unit cost/profit views are clearly marked synthetic planning assumptions.</span></div>
        <FilterBar brand={brand} market={market} availableFilters={dashboard?.available_filters} onBrandChange={handleBrandChange} onMarketChange={setMarket} onReset={resetFilters} />
        <PlanningInputs dashboard={dashboard} brand={brand} market={market} session={planningSession} onPreview={applyPreview} onDiscardAll={discardAll} />

        {loading && <div className="state-card" role="status"><div className="spinner" />Loading planning case…</div>}
        {!loading && error && <div className="state-card error-state" role="alert"><div><strong>Dashboard unavailable</strong><p>{error.message}</p></div><button className="button" type="button" onClick={() => setRetryCount((count) => count + 1)}>Retry</button></div>}
        {!loading && !error && dashboard && (
          <div className="dashboard-stack">
            {dashboard.business_unit_variances.length > 0 ? <>
              <KpiGrid kpis={dashboard.kpis} />
              <MonthlyTrendChart data={dashboard.monthly_trend} />
              <VarianceTable rows={dashboard.business_unit_variances} />
              <div className="two-column"><PvmBridge bridge={dashboard.pvm_bridge} /><ManagementInsights insights={dashboard.management_insights} /></div>
            </> : <div className="state-card empty-dashboard" role="status"><div><strong>No business unit matches the selected filters</strong><p>Choose a valid brand and market combination to view planning metrics.</p></div></div>}
            {dashboard.scenario_comparison && <section className="panel scenario-panel"><div className="section-heading"><h2>Scenario comparison</h2><span className="unit-note">Selected FY Forecast vs Base FY Forecast</span></div><div className="scenario-grid">{(['revenue', 'gross_profit', 'operating_profit'] as const).map((metric) => { const item = dashboard.scenario_comparison![metric]; return <div key={metric}><span>{metric.replaceAll('_', ' ')}</span><strong>{item.selected_fy_forecast.toFixed(1)}</strong><em className={item.delta >= 0 ? 'positive' : 'negative'}>{item.delta >= 0 ? '+' : ''}{item.delta.toFixed(1)} vs base</em></div> })}</div></section>}
            {dashboard.category_detail && <section className="panel table-panel category-detail-panel"><div className="section-heading"><div><h2>Product Category Detail</h2><span className="unit-note">Filtered synthetic allocation · selected {dashboard.selected_plan_variant || 'base'}</span></div></div><div className="synthetic-disclosure">Synthetic planning input — not reported category data</div><div className="table-scroll"><table><thead><tr><th>Period</th><th>Business unit</th><th>Category</th><th>Revenue</th><th>Revenue mix</th><th>Gross margin</th><th>Opex ratio</th><th>Operating margin</th><th>Provenance</th></tr></thead><tbody>{selectedCategoryDetail.map((row) => <tr key={`${row.plan_variant}-${row.period}-${row.business_unit}-${row.category_id}`}><td>{row.period}</td><td>{row.business_unit}</td><td className="table-primary">{row.category_name}</td><td>{row.revenue.toFixed(1)}</td><td>{(row.revenue_mix_pct * 100).toFixed(1)}%</td><td>{(row.gross_margin_pct * 100).toFixed(1)}%</td><td>{(row.opex_ratio_pct * 100).toFixed(1)}%</td><td>{(row.operating_margin_pct * 100).toFixed(1)}%</td><td>{row.provenance}</td></tr>)}</tbody></table></div></section>}
            {operatingLoading && <div className="state-card" role="status"><div className="spinner" />Loading operating decision plan…</div>}
            {!operatingLoading && operatingError && <div className="state-card error-state" role="alert"><div><strong>Operating decision plan unavailable</strong><p>{operatingError.message}</p></div><button className="button" type="button" onClick={() => setOperatingRetryCount((count) => count + 1)}>Retry</button></div>}
            {!operatingLoading && !operatingError && operatingPlan && <div className="dashboard-stack">
              <CashBridge workingCapital={operatingPlan.working_capital} cashBridge={operatingPlan.cash_bridge} reconciliation={operatingPlan.reconciliation} />
              <div className="two-column"><ForecastAccuracy accuracy={operatingPlan.forecast_accuracy} /><ScenarioDecisionTable decisionTable={operatingPlan.decision_table} selectedVariant={operatingPlan.plan_variant} /></div>
              <ActionRegister actions={sessionActions} onChange={setSessionActions} />
            </div>}
            <DataProvenance dashboard={dashboard} />
            <div className="export-row"><div><strong>Take this view to your next review</strong><span>Exports the current filters and selected plan variant into an eight-sheet Excel management pack.</span></div><button className="button button-primary" type="button" onClick={download} disabled={exporting || dashboard.business_unit_variances.length === 0}>{exporting ? 'Building workbook…' : 'Export Excel management pack'}</button></div>
          </div>
        )}
      </div>
      <footer className="app-footer"><span>PlanTerm v0.3</span><span>FP&amp;A Planning and Performance Management Workbench</span><span>Public case study · not internal company data</span></footer>
    </main>
  )
}
