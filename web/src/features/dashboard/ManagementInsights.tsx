import type { ManagementInsight } from '@/types/planning'

export function ManagementInsights({ insights }: { insights: ManagementInsight[] }) {
  return (
    <section className="panel insights-panel" aria-labelledby="insights-title">
      <div className="section-heading"><div><div className="eyebrow">Decision support</div><h2 id="insights-title">Management insights</h2></div><span className="unit-note">Deterministic rules</span></div>
      {insights.length === 0 ? <div className="empty-state">No adverse business-unit variance identified.</div> : <div className="insight-grid">{insights.map((insight) => <article className="insight-card" key={insight.business_unit}><div className="insight-top"><span className="status-pill unfavorable">Watch</span><span className="driver-pill">Profit: {insight.profit_driver || insight.driver}</span></div><h3>{insight.title}</h3><p>{insight.message}</p><div className="action"><span>Suggested action</span>{insight.action}</div></article>)}</div>}
    </section>
  )
}
