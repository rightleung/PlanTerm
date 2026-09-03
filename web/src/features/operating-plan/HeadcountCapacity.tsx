import type { WorkforceCapacityResponse, WorkforceCapacityRollup, WorkforceRoleGroup } from '@/types/planning'
import { useI18n } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

const ROLE_GROUPS: WorkforceRoleGroup[] = ['store operations', 'commercial', 'supply chain', 'finance/support']

function rollupMetric(rollup: WorkforceCapacityRollup | undefined, metric: keyof WorkforceCapacityRollup) {
  const value = rollup?.[metric]
  return typeof value === 'number' ? value : null
}

export function HeadcountCapacity({ capacity }: { capacity: WorkforceCapacityResponse }) {
  const { t, locale, formatNumber } = useI18n()
  const amount = (value: number | null | undefined) => value === null || value === undefined || !Number.isFinite(value) ? t('notAvailable') : formatNumber(value)
  const fte = amount
  const rows = capacity.headcount_rows || []
  const selected = capacity.plan_variant
  const unit = capacity.unit === 'RMB millions unless stated otherwise' ? t('rmbMillionsUnlessStated') : capacity.unit
  const productivityBasis = rows[0]?.productivity_basis === 'Revenue / planned FTE (RMB millions per FTE)' ? t('revenuePerPlannedFte') : rows[0]?.productivity_basis || t('revenuePerFte')
  const portfolio = capacity.rollups?.portfolio
  const evidence = capacity.reconciliation_evidence || { status: 'Not available' }
  const delta = capacity.selected_vs_base_delta || {}
  return <section className="panel table-panel" aria-labelledby="workforce-capacity-title">
    <div className="section-heading"><div><div className="eyebrow">{t('operatingPlanning')}</div><h2 id="workforce-capacity-title">{t('workforceCapacity')}</h2></div><span className="unit-note">{t('selected')} {apiLabel(selected, t)} · {unit}</span></div>
    <div className="synthetic-disclosure">{locale === 'en' ? capacity.disclosure || t('workforceDisclosure') : t('workforceDisclosure')}</div>
    <p className="panel-footnote">{t('productivityBasis')}: {productivityBasis} · {t('roleGroupPlanning')}</p>
    {capacity.locked_rows?.length > 0 && <div className="synthetic-disclosure">{t('lockedHorizon')}</div>}
    <div className="scenario-grid">
      <div><span>{t('portfolioPlannedFte')}</span><strong>{fte(rollupMetric(portfolio, 'planned_fte'))}</strong></div>
      <div><span>{t('requiredFte')}</span><strong>{fte(rollupMetric(portfolio, 'required_fte'))}</strong></div>
      <div><span>{t('capacityGap')}</span><strong>{fte(rollupMetric(portfolio, 'capacity_gap'))}</strong></div>
      <div><span>{t('loadedCost')}</span><strong>{amount(rollupMetric(portfolio, 'loaded_cost'))}</strong></div>
      <div><span>{t('variantDelta')}</span><strong>{amount(delta.loaded_cost ?? null)}</strong></div>
    </div>
    <div className="table-scroll" role="region" tabIndex={0} aria-label={t('workforceCapacity')}><table><thead><tr><th>{t('roleGroup')}</th><th>{t('plannedFte')}</th><th>{t('requiredFte')}</th><th>{t('capacityGap')}</th><th>{t('loadedCost')}</th><th>{t('revenuePerFte')}</th><th>{t('variantDelta')}</th><th>{t('status')}</th><th>{t('provenance')}</th></tr></thead><tbody>
      {ROLE_GROUPS.map((role) => { const summary = capacity.rollups?.role_group?.[role]; const roleRows = rows.filter((row) => row.role_group === role); const revenue = roleRows.reduce((total, row) => total + (Number.isFinite(row.revenue) ? row.revenue : 0), 0); const planned = rollupMetric(summary, 'planned_fte') || 0; const revenuePerFte = planned > 0 ? revenue / planned : null; const status = roleRows.some((row) => row.status === 'capacity_gap') ? 'capacity_gap' : roleRows.some((row) => row.status === 'over_capacity') ? 'over_capacity' : roleRows.length > 0 && roleRows.every((row) => row.status === 'zero_capacity') ? 'zero_capacity' : 'balanced'; return <tr key={role}><td className="table-primary">{apiLabel(role, t)}</td><td>{fte(rollupMetric(summary, 'planned_fte'))}</td><td>{fte(rollupMetric(summary, 'required_fte'))}</td><td>{fte(rollupMetric(summary, 'capacity_gap'))}</td><td>{amount(rollupMetric(summary, 'loaded_cost'))}</td><td>{amount(revenuePerFte)}</td><td>{amount(delta[`${role}.loaded_cost`] ?? null)}</td><td>{apiLabel(status, t)}</td><td>{apiLabel(summary?.provenance || capacity.provenance, t)}</td></tr> })}
      <tr><td className="table-primary">{t('portfolioTotal')}</td><td>{fte(rollupMetric(portfolio, 'planned_fte'))}</td><td>{fte(rollupMetric(portfolio, 'required_fte'))}</td><td>{fte(rollupMetric(portfolio, 'capacity_gap'))}</td><td>{amount(rollupMetric(portfolio, 'loaded_cost'))}</td><td>{amount((rollupMetric(portfolio, 'planned_fte') || 0) > 0 ? (rows.reduce((t, r) => t + r.revenue, 0) / (rollupMetric(portfolio, 'planned_fte') || 1)) : null)}</td><td>{amount(delta.loaded_cost ?? null)}</td><td>{apiLabel(evidence.status, t)}</td><td>{apiLabel(capacity.provenance, t)}</td></tr>
    </tbody></table></div>
    <p className={`reconciliation ${evidence.status === 'reconciled' ? 'ok' : 'bad'}`}>{t('capacityReconciliation', { status: apiLabel(evidence.status, t), residual: amount(evidence.residual ?? evidence.max_residual ?? null), tolerance: amount(evidence.tolerance_rmb_millions ?? null), doubleCounting: evidence.no_double_counting === true ? t('noDoubleCounting') : '' })}</p>
  </section>
}
