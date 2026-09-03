import type { ScenarioDecisionRow } from '@/types/planning'
import { useI18n } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

export function ScenarioDecisionTable({ decisionTable, selectedVariant }: { decisionTable: ScenarioDecisionRow[]; selectedVariant: string }) {
  const { t, formatNumber, formatDate } = useI18n()
  const amount = (value: number | null) => value === null ? t('notAvailable') : formatNumber(value)
  const delta = (value: number | null) => value === null ? t('notAvailable') : `${value >= 0 ? '+' : ''}${formatNumber(value)}`
  const rows = decisionTable || []
  return <section className="panel table-panel" aria-labelledby="decision-table-title">
    <div className="section-heading"><div><div className="eyebrow">{t('decisionSupport')}</div><h2 id="decision-table-title">{t('scenarioDecisionTable')}</h2></div><span className="unit-note">{t('selected')} {apiLabel(selectedVariant, t)} · {t('rmbMillions')}</span></div>
    <div className="synthetic-disclosure">{t('scenarioOutcomes')}</div>
    {rows.length === 0 ? <div className="empty-state" role="status">{t('noScenarioRows')}</div> : <div className="table-scroll" role="region" tabIndex={0} aria-label={t('scenarioDecisionTable')}><table><thead><tr><th>{t('planVariant')}</th><th>{t('fyRevenueDelta')}</th><th>{t('fyOpDelta')}</th><th>{t('cashHeadroom')}</th><th>{t('minimumCashMonth')}</th><th>{t('ccc')}</th><th>{t('owner')}</th><th>{t('nextReview')}</th><th>{t('provenance')}</th></tr></thead><tbody>{rows.map((row) => <tr key={row.plan_variant}><td className="table-primary">{apiLabel(row.plan_variant, t)}</td><td className={row.fy_revenue_delta !== null && row.fy_revenue_delta < 0 ? 'negative' : 'positive'}>{delta(row.fy_revenue_delta)}</td><td className={row.fy_operating_profit_delta !== null && row.fy_operating_profit_delta < 0 ? 'negative' : 'positive'}>{delta(row.fy_operating_profit_delta)}</td><td>{amount(row.cash_headroom)}</td><td>{row.minimum_cash_month ? formatDate(row.minimum_cash_month) : t('notAvailable')}</td><td>{amount(row.ccc)}</td><td>{row.owner ? apiLabel(row.owner, t) : t('notAvailable')}</td><td>{row.next_review_date ? formatDate(row.next_review_date) : t('notAvailable')}</td><td>{apiLabel(row.provenance, t)}</td></tr>)}</tbody></table></div>}
  </section>
}
