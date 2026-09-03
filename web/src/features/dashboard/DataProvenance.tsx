import type { DashboardResponse } from '@/types/planning'
import { useI18n } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

export function DataProvenance({ dashboard }: { dashboard: DashboardResponse }) {
  const { t, formatNumber } = useI18n()
  const percent = (value: number) => `${formatNumber(value * 100)}%`
  const assumptions = dashboard.assumptions
  return (
    <section className="panel provenance-panel" aria-labelledby="provenance-title">
      <div className="section-heading"><div><div className="eyebrow">{t('auditTrail')}</div><h2 id="provenance-title">{t('assumptionsSources')}</h2></div><span className="unit-note">{t('publicSynthetic')}</span></div>
      <div className="provenance-grid"><div><h3>{t('planningAssumptions')}</h3><div className="assumption-list">{Object.entries(assumptions.budget_assumptions).map(([unit, value]) => <div className="assumption-row" key={unit}><span>{apiLabel(unit, t)}</span><span>{percent(value.revenue_growth_vs_fy2025)} {t('growth')} · {percent(value.budget_gross_margin)} GM · {percent(value.budget_operating_margin)} OM · RMB {formatNumber(value.average_ticket)} {t('ticket')}</span></div>)}</div><h3>{t('syntheticProfitAllocation')}</h3><div className="assumption-list">{Object.entries(assumptions.profit_allocation_indices).map(([unit, value]) => <div className="assumption-row" key={unit}><span>{apiLabel(unit, t)}</span><span>{t('gmIndex')} {formatNumber(value.gross_margin_index, { maximumFractionDigits: 2 })} · {t('omIndex')} {formatNumber(value.operating_margin_index, { maximumFractionDigits: 2 })}</span></div>)}</div><p className="disclaimer">{t('syntheticAllocationDisclosure')}</p></div><div><h3>{t('officialDataSources')}</h3><div className="source-list">{dashboard.data_sources.map((source) => <a href={source.url} target="_blank" rel="noreferrer" key={source.url}><span>{apiLabel(source.name, t)}</span><small>{source.source_date} · {apiLabel(source.scope, t)}</small></a>)}</div></div></div>
      <div className="legend"><h3>{t('provenanceLegend')}</h3>{Object.entries(dashboard.provenance_legend).map(([key, value]) => <span key={key}><i className={`legend-dot ${key}`} />{apiLabel(key, t)}: {value}</span>)}</div>
    </section>
  )
}
