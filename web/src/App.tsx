import { useEffect, useState } from 'react'
import { fetchDashboard, ApiError } from '@/api/client'
import { exportManagementPack } from '@/export/managementPack'
import { DataProvenance } from '@/features/dashboard/DataProvenance'
import { FilterBar } from '@/features/dashboard/FilterBar'
import { KpiGrid } from '@/features/dashboard/KpiGrid'
import { ManagementInsights } from '@/features/dashboard/ManagementInsights'
import { MonthlyTrendChart } from '@/features/dashboard/MonthlyTrendChart'
import { PvmBridge } from '@/features/dashboard/PvmBridge'
import { VarianceTable } from '@/features/dashboard/VarianceTable'
import type { BrandFilter, DashboardResponse, MarketFilter } from '@/types/planning'

const CASE_ID = 'miniso-2026'

export default function App() {
  const [brand, setBrand] = useState<BrandFilter>('all')
  const [market, setMarket] = useState<MarketFilter>('all')
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [exporting, setExporting] = useState(false)
  const [retryCount, setRetryCount] = useState(0)

  const marketIsAllowed = (nextBrand: BrandFilter, nextMarket: MarketFilter) => {
    if (nextMarket === 'all' || !dashboard) return true
    return dashboard.available_filters.valid_combinations.some((combination) => (nextBrand === 'all' || combination.brand === nextBrand) && combination.market === nextMarket)
  }

  const handleBrandChange = (nextBrand: BrandFilter) => {
    setBrand(nextBrand)
    if (!marketIsAllowed(nextBrand, market)) setMarket('all')
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    fetchDashboard(CASE_ID, brand, market).then((result) => {
      if (active) setDashboard(result)
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason : new Error('Unable to load dashboard'))
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [brand, market, retryCount])

  const resetFilters = () => { setBrand('all'); setMarket('all') }

  const download = async () => {
    if (!dashboard || dashboard.business_unit_variances.length === 0) return
    setExporting(true)
    try { await exportManagementPack(dashboard) } catch (reason: unknown) { setError(reason instanceof Error ? reason : new Error('Excel export failed')) } finally { setExporting(false) }
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand-lockup"><div className="brand-mark">PT</div><div><div className="brand-name">PlanTerm</div><div className="brand-subtitle">FP&amp;A planning workbench</div></div></div>
        <div className="header-meta"><span className="status-dot" />Local case · no live data dependency</div>
      </header>

      <div className="content">
        <section className="hero">
          <div><div className="eyebrow">MINISO Group · Management view</div><h1>Portfolio planning &amp; performance</h1><p className="hero-copy">A disciplined view of Actual, Budget, Forecast and Prior Year across the three-business-unit MINISO case.</p></div>
          <div className="hero-side"><span className="case-label">{dashboard?.metadata.name || 'MINISO FP&A Portfolio MVP'}</span><strong>As of {dashboard?.metadata.as_of_date || '2026-06-30'}</strong><span>RMB millions · IFRS basis</span></div>
        </section>

        <div className="callout"><span className="callout-icon">i</span><span>Public reported data anchors H1 Actual and Prior Year. Budget, Forecast, monthly allocations and business-unit cost/profit views are clearly marked synthetic planning assumptions.</span></div>
        <FilterBar brand={brand} market={market} availableFilters={dashboard?.available_filters} onBrandChange={handleBrandChange} onMarketChange={setMarket} onReset={resetFilters} />

        {loading && <div className="state-card" role="status"><div className="spinner" />Loading planning case…</div>}
        {!loading && error && <div className="state-card error-state" role="alert"><div><strong>Dashboard unavailable</strong><p>{error.message}</p></div><button className="button" type="button" onClick={() => setRetryCount((count) => count + 1)}>Retry</button></div>}
        {!loading && !error && dashboard && (
          <div className="dashboard-stack">
            {dashboard.business_unit_variances.length > 0 ? <>
              <KpiGrid kpis={dashboard.kpis} />
              <MonthlyTrendChart data={dashboard.monthly_trend} />
              <VarianceTable rows={dashboard.business_unit_variances} />
              <div className="two-column"><PvmBridge bridge={dashboard.pvm_bridge} /><ManagementInsights insights={dashboard.management_insights} /></div>
            </> : <div className="state-card empty-dashboard" role="status"><div><strong>No business unit matches the selected filters</strong><p>Choose a valid brand and market combination to view planning metrics.</p></div></div>}
            <DataProvenance dashboard={dashboard} />
            <div className="export-row"><div><strong>Take this view to your next review</strong><span>Exports the current brand and market filters into a five-sheet Excel management pack.</span></div><button className="button button-primary" type="button" onClick={download} disabled={exporting || dashboard.business_unit_variances.length === 0}>{exporting ? 'Building workbook…' : 'Export Excel management pack'}</button></div>
          </div>
        )}
      </div>
      <footer className="app-footer"><span>PlanTerm v0.1.1</span><span>FP&amp;A Planning and Performance Management Workbench</span><span>Public case study · not internal company data</span></footer>
    </main>
  )
}
