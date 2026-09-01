import type { Worksheet } from 'exceljs'
import type { DashboardResponse, KpiSnapshot, PlanningInputRow, VarianceRow } from '@/types/planning'
import { sanitizeSpreadsheetCell } from '@/lib/spreadsheetText'

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

function sanitizeWorkbookText(workbook: { worksheets: Worksheet[] }) {
  workbook.worksheets.forEach((sheet) => sheet.eachRow((row) => row.eachCell((cell) => {
    cell.value = sanitizeSpreadsheetCell(cell.value) as typeof cell.value
  })))
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

export async function exportManagementPack(dashboard: DashboardResponse, scenarioRows: PlanningInputRow[]) {
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

  const category = workbook.addWorksheet('Product Category Detail')
  const selectedVariant = dashboard.selected_plan_variant || 'base'
  const selectedCategoryRows = (dashboard.category_detail || []).filter((row) => row.plan_variant === selectedVariant)
  setTitle(category, `Product Category Detail · ${selectedVariant} · synthetic planning allocation`, 10)
  category.addRow(['Period', 'Plan Variant', 'Business Unit', 'Category', 'Revenue', 'Revenue Mix %', 'Gross Margin %', 'Opex Ratio %', 'Operating Margin %', 'Provenance'])
  selectedCategoryRows.forEach((row) => category.addRow([row.period, row.plan_variant, row.business_unit, row.category_name, nullableNumber(row.revenue), row.revenue_mix_pct, row.gross_margin_pct, row.opex_ratio_pct, row.operating_margin_pct, row.provenance]))
  configureSheet(category, 2, [14, 14, 28, 28, 15, 15, 15, 15, 18, 24])
  formatColumns(category, selectedCategoryRows.map((_, index) => index + 3), [5], [6, 7, 8, 9])

  const provenance = workbook.addWorksheet('Scenario Inputs & Provenance')
  setTitle(provenance, `Scenario Inputs & Provenance · selected ${dashboard.selected_plan_variant || 'base'}`, 9)
  provenance.addRow(['Planning context', 'Value', 'Source / disclosure'])
  provenance.addRow(['Selected plan variant', dashboard.selected_plan_variant || 'base', 'User-selected scenario; applies to H2 Forecast only'])
  provenance.addRow(['Locked horizon', dashboard.planning_horizon ? `through ${dashboard.planning_horizon.locked_through}` : 'through 2026-06', dashboard.planning_horizon ? `Editable ${dashboard.planning_horizon.editable_from} to ${dashboard.planning_horizon.editable_to}` : 'Editable 2026-07 to 2026-12'])
  provenance.addRow(['Planning input source', dashboard.planning_input_source || 'seed', 'Stateless browser session; server validation authoritative'])
  provenance.addRow(['Synthetic-data disclosure', dashboard.assumptions.note, 'Synthetic allocation/plan; not category-level public reporting'])
  provenance.addRow([])
  provenance.addRow(['Category ID', 'Planning Category', 'Brand', 'Market', 'Business Unit mapping', 'Provenance'])
  ;(dashboard.category_taxonomy_disclosure?.categories || []).forEach((item) => provenance.addRow([item.category_id, item.category_name, item.brand, item.market, item.business_unit, item.provenance]))
  provenance.addRow([]); provenance.addRow(['Official label registry'])
  provenance.addRow(['Official source label', 'Brand', 'Planning category ID', 'Source URL', 'Source period', 'Taxonomy provenance'])
  ;(dashboard.category_taxonomy_disclosure?.official_label_registry || []).forEach((item) => provenance.addRow([item.source_label, item.brand, item.planning_category_id, item.source_url, item.source_period, dashboard.category_taxonomy_disclosure?.taxonomy_provenance || 'official_product_taxonomy_labels']))
  const officialSource = dashboard.category_taxonomy_disclosure?.official_source
  provenance.addRow([]); provenance.addRow(['Official taxonomy note', dashboard.category_taxonomy_disclosure?.official_taxonomy_note || 'Official labels are taxonomy provenance only.'])
  provenance.addRow(['Official source', officialSource ? `${officialSource.publisher} · ${officialSource.document_title} · ${officialSource.source_period} · ${officialSource.source_url}` : 'Not supplied'])
  provenance.addRow(['Disclosure', dashboard.category_taxonomy_disclosure?.disclosure || 'Synthetic planning allocation; not reported category data.'])
  provenance.addRow([]); provenance.addRow(['Canonical 252-row scenario input matrix'])
  provenance.addRow(['case_id', 'plan_variant', 'period', 'business_unit', 'category_id', 'volume_change_pct', 'average_ticket_change_pct', 'gross_margin_delta_pp', 'opex_ratio_delta_pp'])
  scenarioRows.forEach((row) => provenance.addRow([row.case_id, row.plan_variant, row.period, row.business_unit, row.category_id, row.volume_change_pct, row.average_ticket_change_pct, row.gross_margin_delta_pp, row.opex_ratio_delta_pp]))
  const matrixHeader = provenance.rowCount - scenarioRows.length
  configureSheet(provenance, matrixHeader, [18, 16, 14, 30, 34, 22, 28, 24, 22])
  formatColumns(provenance, scenarioRows.map((_, index) => matrixHeader + 1 + index), [], [6, 7, 8, 9])
  const percentColumns = new Map<string, number[]>([
    ['Executive Summary', [5, 7]],
    ['Business Unit Variance', [5, 6, 7]],
    ['Product Category Detail', [6, 7, 8, 9]],
  ])
  for (const [sheetName, columns] of percentColumns) {
    const sheet = workbook.getWorksheet(sheetName)
    sheet?.eachRow((_row, rowNumber) => {
      if (rowNumber <= (sheetName === 'Executive Summary' ? 6 : 2)) return
      columns.forEach((columnNumber) => { sheet.getCell(rowNumber, columnNumber).numFmt = '0.0%;[Red](0.0%);-' })
    })
  }

  // Sanitize only primitive text cells; Excel formulas and numeric values remain untouched.
  sanitizeWorkbookText(workbook)

  const buffer = await workbook.xlsx.writeBuffer()
  saveAs(new Blob([buffer]), FILE_NAME)
  return FILE_NAME
}
