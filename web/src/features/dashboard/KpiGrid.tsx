import type { KpiSnapshot } from '@/types/planning'
import { useI18n } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

export function KpiGrid({ kpis }: { kpis: KpiSnapshot[] }) {
  const { t, formatNumber, formatCurrency } = useI18n()
  const money = (value: number | null) => formatCurrency(value, 'CNY', 'millions')
  const percent = (value: number | null) => value === null ? t('notAvailable') : `${formatNumber(value * 100)}%`
  return (
    <section className="kpi-grid" aria-label={t('kpis')}>
      {kpis.map((kpi) => {
        const isMargin = kpi.metric === 'operating_margin'
        const display = isMargin ? percent(kpi.actual_ytd) : money(kpi.actual_ytd)
        const variance = isMargin ? `${kpi.variance_amount === null ? t('notAvailable') : `${kpi.variance_amount >= 0 ? '+' : ''}${formatNumber(kpi.variance_amount * 100)} ${t('points')}`}` : money(kpi.variance_amount)
        return (
          <article className="kpi-card" key={kpi.metric}>
            <div className="eyebrow">{apiLabel(kpi.metric, t)} <span>{t('h1Actual')}</span></div>
            <div className="kpi-value">{display}</div>
            <div className={`kpi-status ${kpi.status?.toLowerCase() || ''}`}>{apiLabel(kpi.status?.toLowerCase(), t)}</div>
            <div className="kpi-detail">{t('vsBudget')} <strong>{variance}</strong></div>
            <div className="kpi-detail">{t('yoy')} <strong>{percent(kpi.yoy_pct)}</strong></div>
          </article>
        )
      })}
    </section>
  )
}
