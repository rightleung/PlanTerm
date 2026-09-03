import type { ManagementInsight } from '@/types/planning'
import { useI18n, type TranslationKey } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

const insightActionKeys: Record<string, TranslationKey> = {
  Volume: 'insightActionVolume',
  Price: 'insightActionPrice',
  Mix: 'insightActionMix',
  'Gross Margin': 'insightActionGrossMargin',
  Opex: 'insightActionOpex',
}

export function ManagementInsights({ insights }: { insights: ManagementInsight[] }) {
  const { t, locale, formatNumber } = useI18n()
  const localizedInsight = (insight: ManagementInsight) => {
    if (locale === 'en') return { title: insight.title, message: insight.message, action: insight.action }
    const numberOrUnavailable = (value: number | null | undefined, options?: Intl.NumberFormatOptions) => value == null ? t('notAvailable') : formatNumber(Math.abs(value), options)
    const forecastGap = insight.forecast_gap == null ? t('notAvailable') : `${insight.forecast_gap >= 0 ? '+' : ''}${formatNumber(insight.forecast_gap)}`
    const actionKey = insightActionKeys[insight.driver]
    return {
      title: t('insightWatchTitle', { businessUnit: apiLabel(insight.business_unit, t) }),
      message: t('insightBelowPlanMessage', {
        revenueVariance: numberOrUnavailable(insight.revenue_variance),
        variancePercent: numberOrUnavailable(insight.revenue_variance_pct, { maximumFractionDigits: 1 }),
        revenueDriver: apiLabel(insight.revenue_driver || insight.driver, t),
        profitDriver: apiLabel(insight.profit_driver || insight.driver, t),
        profitEffect: numberOrUnavailable(insight.profit_driver_amount ?? insight.driver_amount),
        forecastGap,
      }),
      action: actionKey ? t(actionKey) : insight.action,
    }
  }
  return (
    <section className="panel insights-panel" aria-labelledby="insights-title">
      <div className="section-heading"><div><div className="eyebrow">{t('decisionSupport')}</div><h2 id="insights-title">{t('managementInsights')}</h2></div><span className="unit-note">{t('deterministicRules')}</span></div>
      {insights.length === 0 ? <div className="empty-state">{t('noAdverseVariance')}</div> : <div className="insight-grid">{insights.map((insight) => { const copy = localizedInsight(insight); return <article className="insight-card" key={insight.business_unit}><div className="insight-top"><span className="status-pill unfavorable">{t('watch')}</span><span className="driver-pill">{t('profit')}: {apiLabel(insight.profit_driver || insight.driver, t)}</span></div><h3>{copy.title}</h3><p>{copy.message}</p><div className="action"><span>{t('suggestedAction')}</span>{copy.action}</div></article> })}</div>}
    </section>
  )
}
