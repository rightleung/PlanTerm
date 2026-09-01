import type { DashboardResponse, OperatingPlanResponse, ProvenanceLabel } from '@/types/planning'

export const ASSUMPTION_VERSION = 'miniso-2026@2026-06-30'
export const GIT_SHA = 'unavailable-local-build'

type Conclusion = { metric: string; formula: string; source: string; provenance: ProvenanceLabel; reconciliation: string }
const PUBLIC_ANCHOR_METRICS = new Set(['revenue', 'gross_profit', 'operating_profit'])

export function ProvenancePanel({ dashboard, operatingPlan }: { dashboard: DashboardResponse; operatingPlan?: OperatingPlanResponse | null }) {
  const dashboardReconciliation = dashboard.pvm_bridge.reconciliation_difference !== null && Math.abs(dashboard.pvm_bridge.reconciliation_difference) <= 0.01 ? 'reconciled' : 'not_reconciled'
  const conclusions: Conclusion[] = dashboard.kpis.map((kpi) => {
    const derived = kpi.metric === 'operating_margin' || kpi.variance_amount !== null
    const isPortfolioView = dashboard.selected_filters.brand === 'all' && dashboard.selected_filters.market === 'all'
    const actualProvenance = kpi.actual_ytd === null ? 'synthetic_plan' : isPortfolioView && PUBLIC_ANCHOR_METRICS.has(kpi.metric) ? 'public_reported' : 'synthetic_allocation'
    const budgetProvenance = kpi.budget_ytd === null ? 'synthetic_plan' : 'synthetic_plan'
    return {
      metric: kpi.label,
      formula: `${kpi.metric}: Actual - Budget; forecast gap = Forecast - FY budget`,
      source: derived
        ? `Calculated result · Actual input: ${actualProvenance}; Budget input: ${budgetProvenance}`
        : `Planning input · Actual input: ${actualProvenance}; Budget input: ${budgetProvenance}`,
      provenance: derived ? 'calculated' : actualProvenance,
      reconciliation: kpi.variance_amount === null ? 'not_eligible' : dashboardReconciliation,
    }
  })
  if (dashboard.category_detail && dashboard.category_detail.length > 0) conclusions.push({ metric: 'Selected H2 category revenue roll-up', formula: 'Sum selected category revenue = business-unit revenue', source: 'Deterministic category scenario allocation', provenance: 'calculated', reconciliation: dashboardReconciliation })
  if (operatingPlan) {
    conclusions.push({ metric: 'Illustrative closing cash', formula: 'Opening cash + net cash change', source: 'Operating-plan case inputs', provenance: 'calculated', reconciliation: operatingPlan.reconciliation.cash_bridge.status })
    operatingPlan.decision_table.forEach((row) => conclusions.push({ metric: `FY ${row.plan_variant} revenue delta`, formula: 'Selected FY2026 revenue - base FY2026 revenue', source: 'Scenario decision table', provenance: row.provenance === 'calculated' ? 'calculated' : 'synthetic_plan', reconciliation: operatingPlan.reconciliation.category_rollup.status }))
    const workforce = operatingPlan.workforce_capacity || operatingPlan.headcount_capacity
    if (workforce) conclusions.push({ metric: 'Portfolio capacity gap', formula: 'Required FTE - planned FTE', source: 'Synthetic role-group workforce plan', provenance: 'calculated', reconciliation: workforce.reconciliation_evidence.status })
  }
  return <section className="panel provenance-panel" aria-labelledby="governance-provenance-title">
    <div className="section-heading"><div><div className="eyebrow">Governance</div><h2 id="governance-provenance-title">Conclusion provenance</h2></div><span className="unit-note">Every conclusion is traceable</span></div>
    <div className="metadata-strip"><span><strong>assumption_version</strong>{dashboard.metadata.assumption_version || ASSUMPTION_VERSION}</span><span><strong>git_sha</strong>{dashboard.metadata.git_sha || GIT_SHA}</span><span><strong>Case / as-of</strong>{dashboard.metadata.case_id} · {dashboard.metadata.as_of_date}</span></div>
    <div className="provenance-legend-row">{(['public_reported', 'synthetic_allocation', 'synthetic_plan', 'calculated'] as ProvenanceLabel[]).map((label) => <span key={label}><i className={`legend-dot ${label}`} />{label.replaceAll('_', ' ')}</span>)}</div>
    <div className="table-scroll"><table><thead><tr><th>Conclusion / metric</th><th>Formula</th><th>Source / provenance label</th><th>Reconciliation</th></tr></thead><tbody>{conclusions.map((item) => <tr key={item.metric}><td className="table-primary">{item.metric}</td><td>{item.formula}</td><td>{item.source} · <strong>{item.provenance}</strong></td><td>{item.reconciliation}</td></tr>)}</tbody></table></div>
    <p className="disclaimer">Public reported data anchors group Actual and Prior Year only. Synthetic allocation and synthetic plan values are deterministic case-study assumptions; calculated values are derived from them. No internal MINISO data is claimed.</p>
  </section>
}
