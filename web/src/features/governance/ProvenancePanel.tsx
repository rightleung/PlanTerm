import type { DashboardResponse, OperatingPlanResponse, ProvenanceLabel } from '@/types/planning'
import { useI18n } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

export const ASSUMPTION_VERSION = 'miniso-2026@2026-06-30'
export const GIT_SHA = 'unavailable-local-build'

type Conclusion = { metric: string; formula: string; source: string; provenance: ProvenanceLabel; reconciliation: string }
const PUBLIC_ANCHOR_METRICS = new Set(['revenue', 'gross_profit', 'operating_profit'])

export function ProvenancePanel({ dashboard, operatingPlan }: { dashboard: DashboardResponse; operatingPlan?: OperatingPlanResponse | null }) {
  const { t } = useI18n()
  const dashboardReconciliation = dashboard.pvm_bridge.reconciliation_difference !== null && Math.abs(dashboard.pvm_bridge.reconciliation_difference) <= 0.01 ? 'reconciled' : 'not_reconciled'
  const conclusions: Conclusion[] = dashboard.kpis.map((kpi) => {
    const derived = kpi.metric === 'operating_margin' || kpi.variance_amount !== null
    const isPortfolioView = dashboard.selected_filters.brand === 'all' && dashboard.selected_filters.market === 'all'
    const actualProvenance = kpi.actual_ytd === null ? 'synthetic_plan' : isPortfolioView && PUBLIC_ANCHOR_METRICS.has(kpi.metric) ? 'public_reported' : 'synthetic_allocation'
    const budgetProvenance = kpi.budget_ytd === null ? 'synthetic_plan' : 'synthetic_plan'
    const metricLabel = apiLabel(kpi.metric, t)
    return {
      metric: metricLabel,
      formula: t('kpiFormula', { metric: metricLabel, actual: t('actual'), budget: t('budget'), forecast: t('forecast') }),
      source: derived
        ? `${t('calculatedResult')} · ${t('actual')} input: ${apiLabel(actualProvenance, t)}; ${t('budget')} input: ${apiLabel(budgetProvenance, t)}`
        : `${t('planningInput')} · ${t('actual')} input: ${apiLabel(actualProvenance, t)}; ${t('budget')} input: ${apiLabel(budgetProvenance, t)}`,
      provenance: derived ? 'calculated' : actualProvenance,
      reconciliation: kpi.variance_amount === null ? 'not_eligible' : dashboardReconciliation,
    }
  })
  if (dashboard.category_detail && dashboard.category_detail.length > 0) conclusions.push({ metric: t('selectedH2CategoryRevenue'), formula: t('categoryRevenueFormula'), source: t('deterministicCategoryAllocation'), provenance: 'calculated', reconciliation: dashboardReconciliation })
  if (operatingPlan) {
    conclusions.push({ metric: t('illustrativeClosingCash'), formula: t('closingCashFormula'), source: t('operatingPlanInputs'), provenance: 'calculated', reconciliation: operatingPlan.reconciliation.cash_bridge.status })
    operatingPlan.decision_table.forEach((row) => conclusions.push({ metric: t('fyVariantRevenueDelta', { variant: row.plan_variant }), formula: t('fyRevenueDeltaFormula'), source: t('scenarioDecisionTable'), provenance: row.provenance === 'calculated' ? 'calculated' : 'synthetic_plan', reconciliation: operatingPlan.reconciliation.category_rollup.status }))
    const workforce = operatingPlan.workforce_capacity || operatingPlan.headcount_capacity
    if (workforce) conclusions.push({ metric: t('portfolioCapacityGap'), formula: t('capacityGapFormula'), source: t('syntheticWorkforcePlan'), provenance: 'calculated', reconciliation: workforce.reconciliation_evidence.status })
  }
  return <section className="panel provenance-panel" aria-labelledby="governance-provenance-title">
    <div className="section-heading"><div><div className="eyebrow">{t('governance')}</div><h2 id="governance-provenance-title">{t('conclusionProvenance')}</h2></div><span className="unit-note">{t('traceable')}</span></div>
    <div className="metadata-strip"><span><strong>{t('assumptionVersion')}</strong>{dashboard.metadata.assumption_version || ASSUMPTION_VERSION}</span><span><strong>{t('gitSha')}</strong>{dashboard.metadata.git_sha || GIT_SHA}</span><span><strong>{t('caseAsOf')}</strong>{dashboard.metadata.case_id} · {dashboard.metadata.as_of_date}</span></div>
    <div className="provenance-legend-row">{(['public_reported', 'synthetic_allocation', 'synthetic_plan', 'calculated'] as ProvenanceLabel[]).map((label) => <span key={label}><i className={`legend-dot ${label}`} />{apiLabel(label, t)}</span>)}</div>
    <div className="table-scroll" role="region" tabIndex={0} aria-label={t('conclusionProvenance')}><table><thead><tr><th>{t('conclusionMetric')}</th><th>{t('formula')}</th><th>{t('sourceProvenance')}</th><th>{t('reconciliation')}</th></tr></thead><tbody>{conclusions.map((item) => <tr key={item.metric}><td className="table-primary">{item.metric}</td><td>{item.formula}</td><td>{item.source} · <strong>{apiLabel(item.provenance, t)}</strong></td><td>{apiLabel(item.reconciliation, t)}</td></tr>)}</tbody></table></div>
    <p className="disclaimer">{t('provenanceDisclosure')}</p>
  </section>
}
