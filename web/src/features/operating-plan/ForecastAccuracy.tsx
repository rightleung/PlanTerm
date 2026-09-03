import type { ForecastAccuracy as ForecastAccuracyData } from '@/types/planning'
import { useI18n } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

export function ForecastAccuracy({ accuracy }: { accuracy: ForecastAccuracyData }) {
  const { t, locale, formatNumber } = useI18n()
  const value = (metric: { value: number | null; unit?: string }) => metric.value === null ? t('notAvailable') : metric.unit === 'percent' || metric.unit === '%' ? `${formatNumber(metric.value * 100)}%` : formatNumber(metric.value, { maximumFractionDigits: 2 })
  const metrics = [
    { metric: 'wape', label: 'WAPE', value: accuracy.wape, unit: 'percent', definition: t('wapeDefinition') },
    { metric: 'bias', label: t('bias'), value: accuracy.bias, unit: 'percent', definition: t('biasDefinition') },
    { metric: 'directional_hit_rate', label: t('directionalHitRate'), value: accuracy.directional_hit_rate, unit: 'percent', definition: t('directionalHitRateDefinition') },
  ]
  return <section className="panel" aria-labelledby="forecast-accuracy-title">
    <div className="section-heading"><div><div className="eyebrow">{t('forecastLearning')}</div><h2 id="forecast-accuracy-title">{t('forecastAccuracy')}</h2></div><span className="unit-note">{t('syntheticCalculated')}</span></div>
    <div className="synthetic-disclosure">{t('forecastAccuracyDisclosure')}</div>
    <div className="scenario-grid">{metrics.map((metric) => <div key={metric.metric}><span>{metric.label}</span><strong>{value(metric)}</strong><em>{accuracy.status ? locale === 'en' ? accuracy.status : apiLabel(accuracy.status, t) : t('noEligibilityStatus')}</em><small className="muted">{metric.definition}</small></div>)}</div>
    <p className="panel-footnote">{t('eligiblePeriods')}: {formatNumber(accuracy.eligible_periods)}. {t('provenance')}: {apiLabel(accuracy.provenance, t)}.</p>
  </section>
}
