import type { VarianceRow } from '@/types/planning'
import { useI18n } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

export function VarianceTable({ rows }: { rows: VarianceRow[] }) {
  const { t, formatNumber } = useI18n()
  const money = (value: number | null) => formatNumber(value)
  const pct = (value: number | null) => value === null ? t('notAvailable') : `${formatNumber(value * 100)}%`
  return (
    <section className="panel table-panel" aria-labelledby="variance-title">
      <div className="section-heading"><div><div className="eyebrow">{t('portfolioRollup')}</div><h2 id="variance-title">{t('businessUnitVariance')}</h2></div><span className="unit-note">{t('ytdActualBudget')}</span></div>
      {rows.length === 0 ? <div className="empty-state">{t('emptyFilters')}</div> : <div className="table-scroll" role="region" tabIndex={0} aria-label={t('businessUnitVariance')}><table><thead><tr><th>{t('businessUnitVariance')}</th><th>{t('revenueActual')}</th><th>{t('budget')}</th><th>{t('variance')}</th><th>{t('variancePercent')}</th><th>{t('grossMargin')}</th><th>{t('operatingProfitVariance')}</th><th>{t('fyForecastGap')}</th><th>{t('revenueDriver')}</th><th>{t('profitDriver')}</th><th>{t('status')}</th></tr></thead><tbody>{rows.map((row) => <tr key={row.business_unit}><td className="table-primary">{apiLabel(row.business_unit, t)}</td><td>{money(row.revenue_actual)}</td><td>{money(row.revenue_budget)}</td><td className={row.revenue_variance !== null && row.revenue_variance < 0 ? 'negative' : 'positive'}>{money(row.revenue_variance)}</td><td>{pct(row.revenue_variance_pct)}</td><td>{pct(row.gross_margin_actual)} <span className="muted">/ {pct(row.gross_margin_budget)}</span></td><td className={row.operating_profit_variance !== null && row.operating_profit_variance < 0 ? 'negative' : 'positive'}>{money(row.operating_profit_variance)}</td><td className={row.forecast_gap !== null && row.forecast_gap < 0 ? 'negative' : 'positive'}>{money(row.forecast_gap)}</td><td><span className="driver-pill">{apiLabel(row.primary_driver, t)}</span></td><td><span className="driver-pill">{apiLabel(row.profit_driver, t)}</span></td><td><span className={`status-pill ${row.status?.toLowerCase() || ''}`}>{apiLabel(row.status?.toLowerCase(), t)}</span></td></tr>)}</tbody></table></div>}
    </section>
  )
}
