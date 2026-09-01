import type { ForecastAccuracy as ForecastAccuracyData } from '@/types/planning'

function value(metric: { value: number | null; unit?: string }) {
  if (metric.value === null) return 'Not available'
  if (metric.unit === 'percent' || metric.unit === '%') return `${(metric.value * 100).toFixed(1)}%`
  return metric.value.toLocaleString('en-US', { maximumFractionDigits: 2 })
}

export function ForecastAccuracy({ accuracy }: { accuracy: ForecastAccuracyData }) {
  const metrics = [
    { metric: 'wape', label: 'WAPE', value: accuracy.wape, unit: 'percent', definition: 'Weighted absolute percentage error for eligible elapsed months.' },
    { metric: 'bias', label: 'Bias', value: accuracy.bias, unit: 'percent', definition: 'Forecast bias as a share of eligible actuals.' },
    { metric: 'directional_hit_rate', label: 'Directional hit rate', value: accuracy.directional_hit_rate, unit: 'percent', definition: 'Share of eligible periods with correct forecast direction.' },
  ]
  return <section className="panel" aria-labelledby="forecast-accuracy-title">
    <div className="section-heading"><div><div className="eyebrow">Forecast learning</div><h2 id="forecast-accuracy-title">Forecast accuracy</h2></div><span className="unit-note">Synthetic / calculated</span></div>
    <div className="synthetic-disclosure">Calculated from synthetic planning snapshots; this is not company-internal forecast accuracy.</div>
    <div className="scenario-grid">{metrics.map((metric) => <div key={metric.metric}><span>{metric.label}</span><strong>{value(metric)}</strong><em>{accuracy.status || 'No eligibility status supplied'}</em><small className="muted">{metric.definition}</small></div>)}</div>
    <p className="panel-footnote">Eligible periods: {accuracy.eligible_periods}. Provenance: {accuracy.provenance}.</p>
  </section>
}
