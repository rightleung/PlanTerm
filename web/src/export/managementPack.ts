import type { Worksheet } from 'exceljs'
import type { DashboardResponse, KpiSnapshot, VarianceRow } from '@/types/planning'

const FILE_NAME = 'PlanTerm_MINISO_2026H1_Management_Pack.xlsx'
const COLORS = {
  navy: '17232D',
  teal: '2D6A62',
  white: 'FFFFFFFF',
  green: '2E8B72',
  greenFill: 'DDF3EA',
  red: 'B6534D',
  redFill: 'FBE4E1',
  border: 'D7E0E3',
}

function nullableNumber(value: number | null) {
  return value === null ? null : Number(value.toFixed(4))
}

function formula(expression: string, result: number | string | null) {
  return { formula: expression, result: result === null ? null : result }
}

function lastColumnLetter(columnCount: number) {
  let value = columnCount
  let result = ''
  while (value > 0) {
    const remainder = (value - 1) % 26
    result = String.fromCharCode(65 + remainder) + result
    value = Math.floor((value - 1) / 26)
  }
  return result
}

function setTitle(sheet: Worksheet, text: string, columnCount: number) {
  const lastColumn = lastColumnLetter(columnCount)
  sheet.mergeCells(`A1:${lastColumn}1`)
  const cell = sheet.getCell('A1')
  cell.value = text
  cell.font = { bold: true, size: 16, color: { argb: COLORS.white } }
  cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: COLORS.navy } }
  cell.alignment = { vertical: 'middle' }
  sheet.getRow(1).height = 26
}

function configureSheet(sheet: Worksheet, headerRow: number, columnWidths: number[]) {
  const lastColumn = lastColumnLetter(columnWidths.length)
  sheet.views = [{ state: 'frozen', ySplit: headerRow }]
  sheet.autoFilter = { from: `A${headerRow}`, to: `${lastColumn}${headerRow}` }
  columnWidths.forEach((width, index) => { sheet.getColumn(index + 1).width = width })
  const header = sheet.getRow(headerRow)
  header.font = { bold: true, color: { argb: COLORS.white } }
  header.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: COLORS.teal } }
  header.alignment = { vertical: 'middle', wrapText: true }
  header.height = 22
  header.eachCell((cell) => { cell.border = { bottom: { style: 'thin', color: { argb: COLORS.border } } } })
}

function formatColumns(sheet: Worksheet, rows: number[], numberColumns: number[], percentageColumns: number[] = []) {
  rows.forEach((rowNumber) => {
    numberColumns.forEach((columnNumber) => { sheet.getCell(rowNumber, columnNumber).numFmt = '#,##0.0;[Red](#,##0.0);-' })
    percentageColumns.forEach((columnNumber) => { sheet.getCell(rowNumber, columnNumber).numFmt = '0.0%;[Red](0.0%);-' })
  })
}

function addStatusConditionalFormatting(sheet: Worksheet, range: string) {
  sheet.addConditionalFormatting({
    ref: range,
    rules: [
      { type: 'containsText', operator: 'containsText', text: 'Favorable', priority: 1, style: { font: { color: { argb: COLORS.green } }, fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: COLORS.greenFill } } } },
      { type: 'containsText', operator: 'containsText', text: 'Unfavorable', priority: 2, style: { font: { color: { argb: COLORS.red } }, fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: COLORS.redFill } } } },
    ],
  })
}

function addStatusValue(cell: ReturnType<Worksheet['getCell']>, status: string | null) {
  if (status === 'Favorable') cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: COLORS.greenFill } }
  if (status === 'Unfavorable') cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: COLORS.redFill } }
}

function addSummaryRows(sheet: Worksheet, kpis: KpiSnapshot[]) {
  kpis.forEach((kpi, index) => {
    const rowNumber = 7 + index
    sheet.addRow([
      kpi.label,
      nullableNumber(kpi.actual_ytd),
      nullableNumber(kpi.budget_ytd),
      formula(`IF(OR(B${rowNumber}="",C${rowNumber}=""),"",B${rowNumber}-C${rowNumber})`, nullableNumber(kpi.variance_amount)),
      formula(`IFERROR(D${rowNumber}/ABS(C${rowNumber}),"")`, kpi.variance_pct),
      nullableNumber(kpi.prior_year_ytd),
      formula(`IFERROR((B${rowNumber}-F${rowNumber})/ABS(F${rowNumber}),"")`, kpi.yoy_pct),
      nullableNumber(kpi.fy_budget),
      nullableNumber(kpi.fy_forecast),
      formula(`IF(OR(H${rowNumber}="",I${rowNumber}=""),"",I${rowNumber}-H${rowNumber})`, nullableNumber(kpi.forecast_gap)),
      formula(`IF(E${rowNumber}="","",IF(ABS(E${rowNumber})<=1%,"Neutral",IF(E${rowNumber}>0,"Favorable","Unfavorable")))`, kpi.status),
    ])
    addStatusValue(sheet.getCell(rowNumber, 11), kpi.status)
  })
}

function addVarianceRows(sheet: Worksheet, rows: VarianceRow[]) {
  rows.forEach((row, index) => {
    const rowNumber = 3 + index
    sheet.addRow([
      row.business_unit,
      nullableNumber(row.revenue_actual),
      nullableNumber(row.revenue_budget),
      formula(`IF(OR(B${rowNumber}="",C${rowNumber}=""),"",B${rowNumber}-C${rowNumber})`, nullableNumber(row.revenue_variance)),
      formula(`IFERROR(D${rowNumber}/ABS(C${rowNumber}),"")`, row.revenue_variance_pct),
      nullableNumber(row.gross_margin_actual),
      nullableNumber(row.gross_margin_budget),
      nullableNumber(row.operating_profit_actual),
      nullableNumber(row.operating_profit_budget),
      formula(`IF(OR(H${rowNumber}="",I${rowNumber}=""),"",H${rowNumber}-I${rowNumber})`, nullableNumber(row.operating_profit_variance)),
      nullableNumber(row.fy_budget),
      nullableNumber(row.fy_forecast),
      formula(`IF(OR(K${rowNumber}="",L${rowNumber}=""),"",L${rowNumber}-K${rowNumber})`, nullableNumber(row.forecast_gap)),
      row.primary_driver || null,
      row.profit_driver || null,
      nullableNumber(row.profit_driver_amount),
      formula(`IF(E${rowNumber}="","",IF(ABS(E${rowNumber})<=1%,"Neutral",IF(E${rowNumber}>0,"Favorable","Unfavorable")))`, row.status),
    ])
    addStatusValue(sheet.getCell(rowNumber, 17), row.status)
  })
}

export async function exportManagementPack(dashboard: DashboardResponse) {
  const [{ Workbook }, { saveAs }] = await Promise.all([import('exceljs'), import('file-saver')])
  const workbook = new Workbook()
  workbook.creator = 'PlanTerm'
  workbook.created = new Date('2026-06-30T00:00:00Z')

  const summary = workbook.addWorksheet('Executive Summary')
  setTitle(summary, `PlanTerm · ${dashboard.metadata.name}`, 11)
  summary.addRow(['Filter', `${dashboard.selected_filters.brand} / ${dashboard.selected_filters.market}`])
  summary.addRow(['As of', dashboard.metadata.as_of_date])
  summary.addRow(['Unit', dashboard.metadata.unit])
  summary.addRow([])
  summary.addRow(['KPI', 'H1 Actual', 'H1 Budget', 'Variance', 'Variance %', 'Prior Year', 'YoY %', 'FY Budget', 'FY Forecast', 'Forecast Gap', 'Status'])
  addSummaryRows(summary, dashboard.kpis)
  configureSheet(summary, 6, [24, 15, 15, 15, 13, 15, 13, 15, 15, 15, 15])
  formatColumns(summary, dashboard.kpis.map((_, index) => 7 + index), [2, 3, 4, 6, 8, 9, 10], [5, 7])
  addStatusConditionalFormatting(summary, `K7:K${6 + dashboard.kpis.length}`)

  const trend = workbook.addWorksheet('Monthly Trend')
  setTitle(trend, 'Monthly Revenue Trend · RMB millions', 5)
  trend.addRow(['Period', 'Actual', 'Budget', 'Forecast', 'Prior Year'])
  dashboard.monthly_trend.forEach((point) => trend.addRow([point.period, nullableNumber(point.actual), nullableNumber(point.budget), nullableNumber(point.forecast), nullableNumber(point.prior_year)]))
  configureSheet(trend, 2, [15, 16, 16, 16, 16])
  formatColumns(trend, dashboard.monthly_trend.map((_, index) => 3 + index), [2, 3, 4, 5])

  const variance = workbook.addWorksheet('Business Unit Variance')
  setTitle(variance, 'Business Unit Variance · RMB millions', 17)
  variance.addRow(['Business Unit', 'Revenue Actual', 'Revenue Budget', 'Variance', 'Variance %', 'Gross Margin Actual', 'Gross Margin Budget', 'Operating Profit Actual', 'Operating Profit Budget', 'Operating Profit Variance', 'FY Budget', 'FY Forecast', 'Forecast Gap', 'Revenue Driver', 'Profit Driver', 'Profit Driver Amount', 'Status'])
  addVarianceRows(variance, dashboard.business_unit_variances)
  configureSheet(variance, 2, [28, 15, 15, 15, 13, 16, 16, 18, 18, 20, 15, 15, 15, 16, 16, 18, 15])
  formatColumns(variance, dashboard.business_unit_variances.map((_, index) => 3 + index), [2, 3, 4, 8, 9, 10, 11, 12, 13, 16], [5, 6, 7])
  addStatusConditionalFormatting(variance, `Q3:Q${2 + dashboard.business_unit_variances.length}`)

  const pvm = workbook.addWorksheet('PVM Bridge')
  setTitle(pvm, 'Price / Volume / Mix Bridge · RMB millions', 2)
  pvm.addRow(['Bridge item', 'Amount'])
  pvm.addRow(['Actual revenue', nullableNumber(dashboard.pvm_bridge.actual_revenue)])
  pvm.addRow(['Budget revenue', nullableNumber(dashboard.pvm_bridge.budget_revenue)])
  pvm.addRow(['Volume', nullableNumber(dashboard.pvm_bridge.volume)])
  pvm.addRow(['Mix', nullableNumber(dashboard.pvm_bridge.mix)])
  pvm.addRow(['Price', nullableNumber(dashboard.pvm_bridge.price)])
  pvm.addRow(['Reconciliation difference', formula('SUM(B5:B7)-(B3-B4)', nullableNumber(dashboard.pvm_bridge.reconciliation_difference))])
  configureSheet(pvm, 2, [30, 20])
  formatColumns(pvm, [3, 4, 5, 6, 7, 8], [2])

  const assumptions = workbook.addWorksheet('Assumptions & Sources')
  setTitle(assumptions, 'Assumptions & Sources', 4)
  assumptions.addRow(['Source type', 'Item', 'Detail', 'Provenance'])
  Object.entries(dashboard.assumptions.budget_assumptions).forEach(([unit, value]) => assumptions.addRow(['Synthetic plan', unit, `Revenue growth ${value.revenue_growth_vs_fy2025}; GM ${value.budget_gross_margin}; OM ${value.budget_operating_margin}; ticket RMB ${value.average_ticket}`, 'Synthetic plan']))
  Object.entries(dashboard.assumptions.profit_allocation_indices).forEach(([unit, value]) => {
    assumptions.addRow(['Synthetic allocation', `${unit} · Gross-margin index`, value.gross_margin_index, 'Synthetic allocation'])
    assumptions.addRow(['Synthetic allocation', `${unit} · Operating-margin index`, value.operating_margin_index, 'Synthetic allocation'])
  })
  Object.entries(dashboard.assumptions.h2_forecast_adjustment_vs_budget).forEach(([unit, value]) => assumptions.addRow(['Synthetic plan', `${unit} · H2 forecast adjustment`, value, 'Synthetic plan']))
  dashboard.data_sources.forEach((source) => assumptions.addRow(['Public reported', source.name, `${source.source_date} · ${source.scope} · ${source.url}`, 'Public reported']))
  assumptions.addRow(['Synthetic plan', 'Disclosure', dashboard.assumptions.note, 'Synthetic plan'])
  configureSheet(assumptions, 2, [22, 38, 86, 22])
  const assumptionRows = Array.from({ length: assumptions.rowCount - 2 }, (_, index) => index + 3)
  formatColumns(assumptions, assumptionRows, [3])

  const percentColumns = new Map<string, number[]>([
    ['Executive Summary', [5, 7]],
    ['Business Unit Variance', [5, 6, 7]],
  ])
  for (const [sheetName, columns] of percentColumns) {
    const sheet = workbook.getWorksheet(sheetName)
    sheet?.eachRow((_row, rowNumber) => {
      if (rowNumber <= (sheetName === 'Executive Summary' ? 6 : 2)) return
      columns.forEach((columnNumber) => { sheet.getCell(rowNumber, columnNumber).numFmt = '0.0%;[Red](0.0%);-' })
    })
  }

  const buffer = await workbook.xlsx.writeBuffer()
  saveAs(new Blob([buffer]), FILE_NAME)
  return FILE_NAME
}
