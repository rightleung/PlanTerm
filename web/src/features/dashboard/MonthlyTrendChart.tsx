import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { MonthlyTrendPoint } from '@/types/planning'

const colors = { actual: '#e7f0ea', budget: '#6fb5a3', forecast: '#e6b968', prior_year: '#647080' }

export function MonthlyTrendChart({ data }: { data: MonthlyTrendPoint[] }) {
  const chartData = data.map((point) => ({ ...point, month: point.period.slice(5) }))
  return (
    <section className="panel chart-panel" aria-labelledby="monthly-trend-title">
      <div className="section-heading">
        <div><div className="eyebrow">Performance cadence</div><h2 id="monthly-trend-title">Monthly revenue trend</h2></div>
        <span className="unit-note">RMB millions</span>
      </div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#25313b" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="month" tick={{ fill: '#8793a1', fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#8793a1', fontSize: 12 }} axisLine={false} tickLine={false} width={48} tickFormatter={(value) => `${Math.round(value)}`} />
            <Tooltip contentStyle={{ background: '#141c24', border: '1px solid #2c3a45', borderRadius: 8 }} labelStyle={{ color: '#cdd7df' }} formatter={(value) => value == null ? '—' : Number(value).toFixed(1)} />
            <Legend wrapperStyle={{ color: '#a9b4bf', fontSize: 12 }} />
            <Line name="Actual" type="monotone" dataKey="actual" stroke={colors.actual} strokeWidth={3} dot={{ r: 2, fill: colors.actual }} connectNulls={false} />
            <Line name="Budget" type="monotone" dataKey="budget" stroke={colors.budget} strokeWidth={2} strokeDasharray="5 4" dot={false} />
            <Line name="Forecast" type="monotone" dataKey="forecast" stroke={colors.forecast} strokeWidth={2} dot={false} />
            <Line name="Prior Year" type="monotone" dataKey="prior_year" stroke={colors.prior_year} strokeWidth={2} strokeDasharray="2 5" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="panel-footnote">Actual is available through June 2026 only. Future Actual periods remain missing by design.</p>
    </section>
  )
}
