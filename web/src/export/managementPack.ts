import type { DashboardResponse } from '@/types/planning'

const FILE_NAME = 'PlanTerm_MINISO_2026H1_Management_Pack.xlsx'

function formatNumber(value: number | null) {
  return value === null ? '—' : Number(value.toFixed(4))
}

function title(sheet: { mergeCells: (range: string) => void; getCell: (address: string) => { value: unknown; font: object; fill: object } }, text: string) {
  sheet.mergeCells('A1:H1')
  const cell = sheet.getCell('A1')
  cell.value = text
  cell.font = { bold: true, size: 16, color: { argb: 'FFFFFFFF' } }
  cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: '17232D' } }
}

export async function exportManagementPack(dashboard: DashboardResponse) {
  const [{ Workbook }, { saveAs }] = await Promise.all([import('exceljs'), import('file-saver')])
  const workbook = new Workbook()
  workbook.creator = 'PlanTerm'
  workbook.created = new Date('2026-06-30T00:00:00Z')

  const summary = workbook.addWorksheet('Executive Summary')
  title(summary, `PlanTerm · ${dashboard.metadata.name}`)
  summary.addRow(['Filter', `${dashboard.selected_filters.brand} / ${dashboard.selected_filters.market}`])
  summary.addRow(['As of', dashboard.metadata.as_of_date])
  summary.addRow(['Unit', dashboard.metadata.unit])
  summary.addRow([])
  summary.addRow(['KPI', 'H1 Actual', 'H1 Budget', 'Variance', 'Variance %', 'Prior Year', 'YoY %', 'FY Forecast Gap'])
  dashboard.kpis.forEach((kpi) => summary.addRow([kpi.label, formatNumber(kpi.actual_ytd), formatNumber(kpi.budget_ytd), formatNumber(kpi.variance_amount), kpi.variance_pct === null ? '—' : kpi.variance_pct, formatNumber(kpi.prior_year_ytd), kpi.yoy_pct === null ? '—' : kpi.yoy_pct, formatNumber(kpi.forecast_gap)]))

  const trend = workbook.addWorksheet('Monthly Trend')
  title(trend, 'Monthly Revenue Trend · RMB millions')
  trend.addRow(['Period', 'Actual', 'Budget', 'Forecast', 'Prior Year'])
  dashboard.monthly_trend.forEach((point) => trend.addRow([point.period, formatNumber(point.actual), formatNumber(point.budget), formatNumber(point.forecast), formatNumber(point.prior_year)]))

  const variance = workbook.addWorksheet('Business Unit Variance')
  title(variance, 'Business Unit Variance · RMB millions')
  variance.addRow(['Business Unit', 'Revenue Actual', 'Revenue Budget', 'Variance', 'Variance %', 'Op. Margin Actual', 'Op. Margin Budget', 'FY Forecast Gap', 'Primary Driver', 'Status'])
  dashboard.business_unit_variances.forEach((row) => variance.addRow([row.business_unit, formatNumber(row.revenue_actual), formatNumber(row.revenue_budget), formatNumber(row.revenue_variance), row.revenue_variance_pct === null ? '—' : row.revenue_variance_pct, row.operating_margin_actual === null ? '—' : row.operating_margin_actual, row.operating_margin_budget === null ? '—' : row.operating_margin_budget, formatNumber(row.forecast_gap), row.primary_driver || '—', row.status || '—']))

  const pvm = workbook.addWorksheet('PVM Bridge')
  title(pvm, 'Price / Volume / Mix Bridge · RMB millions')
  pvm.addRow(['Bridge item', 'Amount'])
  pvm.addRow(['Actual revenue', formatNumber(dashboard.pvm_bridge.actual_revenue)])
  pvm.addRow(['Budget revenue', formatNumber(dashboard.pvm_bridge.budget_revenue)])
  pvm.addRow(['Volume', formatNumber(dashboard.pvm_bridge.volume)])
  pvm.addRow(['Mix', formatNumber(dashboard.pvm_bridge.mix)])
  pvm.addRow(['Price', formatNumber(dashboard.pvm_bridge.price)])
  pvm.addRow(['Reconciliation difference', formatNumber(dashboard.pvm_bridge.reconciliation_difference)])

  const assumptions = workbook.addWorksheet('Assumptions & Sources')
  title(assumptions, 'Assumptions & Sources')
  assumptions.addRow(['Source type', 'Item', 'Detail'])
  Object.entries(dashboard.assumptions.budget_assumptions).forEach(([unit, value]) => assumptions.addRow(['Synthetic plan', unit, `Revenue growth ${value.revenue_growth_vs_fy2025}; GM ${value.budget_gross_margin}; OM ${value.budget_operating_margin}; ticket RMB ${value.average_ticket}`]))
  dashboard.data_sources.forEach((source) => assumptions.addRow(['Public reported', source.name, `${source.source_date} · ${source.scope} · ${source.url}`]))
  assumptions.addRow(['Synthetic plan', 'Disclosure', dashboard.assumptions.note])

  workbook.eachSheet((sheet) => {
    sheet.views = [{ state: 'frozen', ySplit: 5 }]
    sheet.columns.forEach((column) => { column.width = Math.min(Math.max((column.header?.toString().length || 12) + 4, 14), 42) })
    sheet.getRow(1).height = 26
    sheet.getRow(1).eachCell((cell) => { cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: '17232D' } } })
    sheet.getRow(5).font = { bold: true, color: { argb: 'FFFFFFFF' } }
    sheet.getRow(5).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: '2D6A62' } }
    sheet.eachRow((row, rowNumber) => {
      if (rowNumber > 5) row.eachCell((cell) => { if (typeof cell.value === 'number') cell.numFmt = '#,##0.0;[Red](#,##0.0);-' })
    })
  })

  // Percent columns are stored as true Excel percentages for readable formulas and filters.
  for (const sheetName of ['Executive Summary', 'Business Unit Variance']) {
    const sheet = workbook.getWorksheet(sheetName)
    sheet?.eachRow((row, rowNumber) => { if (rowNumber >= 6) row.eachCell((cell, columnNumber) => { if ([5, 7].includes(columnNumber)) cell.numFmt = '0.0%;[Red](0.0%);-' }) })
  }
  const buffer = await workbook.xlsx.writeBuffer()
  saveAs(new Blob([buffer]), FILE_NAME)
  return FILE_NAME
}
