import type { Worksheet } from 'exceljs'
import type { ActionRegisterRow, DashboardResponse, DecisionLogRow, KpiSnapshot, OperatingPlanResponse, PlanningInputRow, VarianceRow, WorkforceCapacityResponse, WorkforceRoleGroup } from '@/types/planning'
import { sanitizeSpreadsheetCell } from '@/lib/spreadsheetText'
import { ASSUMPTION_VERSION, GIT_SHA } from '@/features/governance/ProvenancePanel'

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
  styleHeader(sheet, headerRow)
}

function styleHeader(sheet: Worksheet, headerRow: number) {
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

function addWorkforceStatusConditionalFormatting(sheet: Worksheet, range: string) {
  sheet.addConditionalFormatting({
    ref: range,
    rules: [
      { type: 'containsText', operator: 'containsText', text: 'capacity_gap', priority: 1, style: { font: { color: { argb: COLORS.red } }, fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: COLORS.redFill } } } },
      { type: 'containsText', operator: 'containsText', text: 'over_capacity', priority: 2, style: { font: { color: { argb: COLORS.green } }, fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: COLORS.greenFill } } } },
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

function addWorkforceSection(sheet: Worksheet, workforce: WorkforceCapacityResponse) {
  const headingRow = sheet.rowCount + 2
  sheet.addRow([])
  sheet.addRow([`Workforce Capacity · ${workforce.plan_variant} · synthetic planning`])
  sheet.addRow(['Workforce disclosure', workforce.disclosure])
  sheet.addRow(['Workforce provenance', workforce.provenance, 'Input provenance', workforce.input_provenance])
  sheet.addRow(['Workforce reconciliation', workforce.reconciliation_evidence?.status || 'Not available', 'Residual', nullableNumber((workforce.reconciliation_evidence?.residual ?? workforce.reconciliation_evidence?.max_residual) as number | null), 'Tolerance', nullableNumber(workforce.reconciliation_evidence?.tolerance_rmb_millions ?? null)])
  const summaryHeaderRow = sheet.rowCount + 1
  sheet.addRow(['Role group', 'Planned FTE', 'Required FTE', 'Capacity gap', 'Loaded cost', 'Revenue / FTE', 'Variant delta', 'Status', 'Provenance'])
  const roles: WorkforceRoleGroup[] = ['store operations', 'commercial', 'supply chain', 'finance/support']
  roles.forEach((role) => {
    const rollup = workforce.rollups?.role_group?.[role]
    const roleRows = workforce.headcount_rows.filter((row) => row.role_group === role)
    const revenue = roleRows.reduce((total, row) => total + (Number.isFinite(row.revenue) ? row.revenue : 0), 0)
    const planned = rollup?.planned_fte || 0
    sheet.addRow([role, nullableNumber(rollup?.planned_fte ?? null), nullableNumber(rollup?.required_fte ?? null), nullableNumber(rollup?.capacity_gap ?? null), nullableNumber(rollup?.loaded_cost ?? null), planned > 0 ? nullableNumber(revenue / planned) : null, nullableNumber((workforce.selected_vs_base_delta || {})[`${role}.loaded_cost`] ?? null), roleRows.some((row) => row.status === 'capacity_gap') ? 'capacity_gap' : roleRows.some((row) => row.status === 'over_capacity') ? 'over_capacity' : roleRows.length > 0 && roleRows.every((row) => row.status === 'zero_capacity') ? 'zero_capacity' : 'balanced', rollup?.provenance || workforce.provenance])
  })
  const portfolio = workforce.rollups?.portfolio
  const portfolioRevenue = workforce.headcount_rows.reduce((total, row) => total + (Number.isFinite(row.revenue) ? row.revenue : 0), 0)
  sheet.addRow(['Portfolio total', nullableNumber(portfolio?.planned_fte ?? null), nullableNumber(portfolio?.required_fte ?? null), nullableNumber(portfolio?.capacity_gap ?? null), nullableNumber(portfolio?.loaded_cost ?? null), (portfolio?.planned_fte || 0) > 0 ? nullableNumber(portfolioRevenue / (portfolio?.planned_fte || 1)) : null, nullableNumber(workforce.selected_vs_base_delta?.loaded_cost ?? null), workforce.reconciliation_evidence?.status || 'Not available', workforce.provenance])
  sheet.addRow([])
  const detailHeaderRow = sheet.rowCount + 1
  sheet.addRow(['Period', 'Business Unit', 'Role Group', 'Planned FTE', 'Required FTE', 'Capacity Gap', 'Loaded Cost', 'Revenue / FTE', 'Status', 'Provenance'])
  workforce.headcount_rows.forEach((row) => sheet.addRow([row.period, row.business_unit, row.role_group, nullableNumber(row.planned_fte), nullableNumber(row.required_fte), nullableNumber(row.capacity_gap), nullableNumber(row.loaded_cost), row.revenue_per_fte === null ? null : nullableNumber(row.revenue_per_fte), row.status, row.provenance]))
  const roleTableStartRow = summaryHeaderRow + 1
  const roleTableEndRow = roleTableStartRow + roles.length
  const detailStartRow = detailHeaderRow + 1
  const detailEndRow = detailStartRow + workforce.headcount_rows.length - 1
  sheet.getRow(headingRow).font = { bold: true }
  styleHeader(sheet, summaryHeaderRow)
  styleHeader(sheet, detailHeaderRow)
  formatColumns(sheet, Array.from({ length: roles.length + 1 }, (_, index) => roleTableStartRow + index), [2, 3, 4, 5, 6, 7])
  formatColumns(sheet, Array.from({ length: workforce.headcount_rows.length }, (_, index) => detailStartRow + index), [4, 5, 6, 7, 8])
  addWorkforceStatusConditionalFormatting(sheet, `H${roleTableStartRow}:H${roleTableEndRow}`)
  addWorkforceStatusConditionalFormatting(sheet, `I${detailStartRow}:I${detailEndRow}`)
}

export async function exportManagementPack(dashboard: DashboardResponse, scenarioRows: PlanningInputRow[], operatingPlan: OperatingPlanResponse | null = null, sessionActions: ActionRegisterRow[] = [], decisionLog: DecisionLogRow[] = []) {
  const [{ Workbook }, { saveAs }] = await Promise.all([import('exceljs'), import('file-saver')])
  const workbook = new Workbook()
  workbook.creator = 'PlanTerm'
  workbook.created = new Date('2026-06-30T00:00:00Z')
  const workforce = operatingPlan?.workforce_capacity || operatingPlan?.headcount_capacity

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
  setTitle(pvm, 'Price / Volume / Mix and Operating Profit Bridges · RMB millions', 6)
  pvm.addRow(['Bridge item', 'Amount'])
  pvm.addRow(['Actual revenue', nullableNumber(dashboard.pvm_bridge.actual_revenue)])
  pvm.addRow(['Budget revenue', nullableNumber(dashboard.pvm_bridge.budget_revenue)])
  pvm.addRow(['Volume', nullableNumber(dashboard.pvm_bridge.volume)])
  pvm.addRow(['Mix', nullableNumber(dashboard.pvm_bridge.mix)])
  pvm.addRow(['Price', nullableNumber(dashboard.pvm_bridge.price)])
  pvm.addRow(['Reconciliation difference', formula('SUM(B5:B7)-(B3-B4)', nullableNumber(dashboard.pvm_bridge.reconciliation_difference))])
  pvm.addRow([])
  pvm.addRow(['Operating Profit bridge · PVM profit effect + GM effect + Opex effect'])
  const profitSummaryHeaderRow = pvm.rowCount + 1
  pvm.addRow(['Driver', 'Amount', '% of OP variance', 'Direction', 'Provenance', 'Action owner'])
  const actualProfitProvenance = dashboard.selected_filters.brand === 'all' && dashboard.selected_filters.market === 'all'
    ? 'public_reported · group anchor'
    : 'synthetic_allocation · allocated BU view'
  const profitActualRow = pvm.rowCount + 1
  pvm.addRow(['Actual operating profit', nullableNumber(dashboard.profit_bridge.actual_operating_profit), null, null, actualProfitProvenance, null])
  const profitBudgetRow = pvm.rowCount + 1
  pvm.addRow(['Budget operating profit', nullableNumber(dashboard.profit_bridge.budget_operating_profit), null, null, 'synthetic_plan', null])
  const profitVarianceRow = pvm.rowCount + 1
  pvm.addRow(['Operating profit variance', formula(`IF(OR(B${profitActualRow}="",B${profitBudgetRow}=""),"",B${profitActualRow}-B${profitBudgetRow})`, nullableNumber(dashboard.profit_bridge.operating_profit_variance)), null, null, 'calculated', null])
  const profitItemsHeaderRow = pvm.rowCount + 1
  pvm.addRow(['Driver', 'Amount', '% of OP variance', 'Direction', 'Provenance', 'Action owner'])
  const profitItemsStartRow = pvm.rowCount + 1
  dashboard.profit_bridge.items.forEach((item) => {
    const rowNumber = pvm.rowCount + 1
    pvm.addRow([item.driver, nullableNumber(item.amount), formula(`IFERROR(B${rowNumber}/ABS(B${profitVarianceRow}),"")`, nullableNumber(item.pct_of_variance)), item.direction, item.provenance, item.action_owner])
  })
  configureSheet(pvm, 2, [34, 20, 20, 16, 24, 34])
  styleHeader(pvm, profitSummaryHeaderRow)
  styleHeader(pvm, profitItemsHeaderRow)
  formatColumns(pvm, [3, 4, 5, 6, 7, 8, profitActualRow, profitBudgetRow, profitVarianceRow, ...Array.from({ length: dashboard.profit_bridge.items.length }, (_, index) => profitItemsStartRow + index)], [2], [3])

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

  const operating = workbook.addWorksheet('Operating Decision')
  const operatingVariant = operatingPlan?.plan_variant || dashboard.selected_plan_variant || 'base'
  const assumptionVersion = operatingPlan?.assumption_registry?.assumption_version || operatingPlan?.assumption_version || dashboard.metadata.assumption_version || ASSUMPTION_VERSION
  const gitSha = operatingPlan?.assumption_registry?.git_sha || operatingPlan?.git_sha || dashboard.metadata.git_sha || GIT_SHA
  const exportedDecisionLog = decisionLog.length > 0 ? decisionLog : (operatingPlan?.decision_log || operatingPlan?.governance?.decision_log || [])
  setTitle(operating, `Operating Decision · ${operatingVariant} · illustrative / synthetic · assumptions ${assumptionVersion} · git ${gitSha}`, 12)
  operating.addRow(['Case', dashboard.metadata.name, 'As of', operatingPlan?.as_of_date || dashboard.metadata.as_of_date, 'Unit', 'RMB millions'])
  operating.addRow(['Disclosure', 'Synthetic planning assumptions and calculated illustrative cash - not public reported or actual cash.'])
  operating.addRow([])
  operating.addRow(['Working capital · synthetic planning inputs and calculated balances'])
  operating.addRow(['Period', 'Business Unit', 'AR Days', 'Inventory Days', 'AP Days', 'AR Balance', 'Inventory Balance', 'AP Balance', 'NWC', 'CCC', 'Provenance'])
  const workingCapitalRows = operatingPlan?.working_capital.rows || []
  workingCapitalRows.forEach((row, index) => {
    const rowNumber = 7 + index
    operating.addRow([
      row.period, row.business_unit, nullableNumber(row.ar_days), nullableNumber(row.inventory_days), nullableNumber(row.ap_days),
      nullableNumber(row.ar_balance), nullableNumber(row.inventory_balance), nullableNumber(row.ap_balance),
      formula(`IF(OR(F${rowNumber}="",G${rowNumber}="",H${rowNumber}=""),"",F${rowNumber}+G${rowNumber}-H${rowNumber})`, nullableNumber(row.nwc)),
      formula(`IF(OR(C${rowNumber}="",D${rowNumber}="",E${rowNumber}=""),"",C${rowNumber}+D${rowNumber}-E${rowNumber})`, nullableNumber(row.ccc)),
      row.provenance,
    ])
  })
  const cashHeadingRow = 8 + workingCapitalRows.length
  operating.addRow([])
  operating.addRow(['Illustrative cash bridge · calculated from synthetic planning assumptions'])
  operating.addRow(['Bridge item', 'Amount', 'Provenance'])
  const latestCash = operatingPlan?.cash_bridge.rows[operatingPlan.cash_bridge.rows.length - 1]
  const cashRows: Array<[string, number | null]> = [
    ['Opening cash', latestCash?.opening_cash ?? null],
    ['Operating profit', latestCash?.operating_profit ?? null],
    ['AR effect', latestCash === undefined || latestCash.prior_ar === null || latestCash.current_ar === null ? null : latestCash.prior_ar - latestCash.current_ar],
    ['Inventory effect', latestCash === undefined || latestCash.prior_inventory === null || latestCash.current_inventory === null ? null : latestCash.prior_inventory - latestCash.current_inventory],
    ['AP effect', latestCash === undefined || latestCash.current_ap === null || latestCash.prior_ap === null ? null : latestCash.current_ap - latestCash.prior_ap],
    ['CAPEX', latestCash?.capex ?? null],
    ['Other cash', latestCash?.other_cash_items ?? null],
  ]
  cashRows.forEach(([label, value]) => operating.addRow([label, nullableNumber(value), label === 'Opening cash' || label === 'CAPEX' || label === 'Other cash' ? 'synthetic_plan' : 'calculated']))
  const cashStartRow = cashHeadingRow + 2
  const netCashRow = cashStartRow + cashRows.length
  operating.addRow(['Net cash change', formula(`IF(COUNT(B${cashStartRow + 1}:B${cashStartRow + 6})<6,"",SUM(B${cashStartRow + 1}:B${cashStartRow + 4})-B${cashStartRow + 5}+B${cashStartRow + 6})`, nullableNumber(latestCash?.net_cash_change ?? null)), 'calculated'])
  operating.addRow(['Illustrative closing cash', formula(`IF(OR(B${cashStartRow}="",B${netCashRow}=""),"",B${cashStartRow}+B${netCashRow})`, nullableNumber(latestCash?.closing_illustrative_cash ?? null)), 'calculated'])
  operating.addRow(['Minimum cash buffer', nullableNumber(latestCash?.minimum_cash_buffer ?? null), 'synthetic_plan'])
  operating.addRow(['Headroom', formula(`IF(OR(B${netCashRow + 1}="",B${netCashRow + 2}=""),"",B${netCashRow + 1}-B${netCashRow + 2})`, nullableNumber(latestCash?.headroom ?? null)), 'calculated'])
  if (workforce) addWorkforceSection(operating, workforce)
  const accuracyHeadingRow = operating.rowCount + 2
  operating.addRow([])
  operating.addRow(['Forecast accuracy · calculated from synthetic snapshots'])
  operating.addRow(['Metric', 'Value', 'Definition', 'Status', 'Provenance'])
  const accuracyRows = [
    ['WAPE', operatingPlan?.forecast_accuracy.wape ?? null, 'Weighted absolute percentage error for eligible elapsed months.'],
    ['Bias', operatingPlan?.forecast_accuracy.bias ?? null, 'Forecast bias as a share of eligible actuals.'],
    ['Directional hit rate', operatingPlan?.forecast_accuracy.directional_hit_rate ?? null, 'Share of eligible periods with correct forecast direction.'],
  ] as const
  accuracyRows.forEach(([label, value, definition]) => operating.addRow([label, nullableNumber(value), definition, operatingPlan?.forecast_accuracy.status || 'Not available', operatingPlan?.forecast_accuracy.provenance || 'calculated']))
  operating.addRow([])
  operating.addRow(['Scenario decision table · selected variant and Base / Upside / Downside deltas'])
  operating.addRow(['Plan Variant', 'FY Revenue Delta', 'FY Operating Profit Delta', 'Cash Headroom', 'Minimum Cash Month', 'CCC', 'Revenue Driver', 'Profit Driver', 'Cash Driver', 'Owner', 'Next Review', 'Provenance'])
  ;(operatingPlan?.decision_table || []).forEach((row) => operating.addRow([row.plan_variant, nullableNumber(row.fy_revenue_delta), nullableNumber(row.fy_operating_profit_delta), nullableNumber(row.cash_headroom), row.minimum_cash_month, nullableNumber(row.ccc), row.top_revenue_driver, row.top_profit_driver, row.top_cash_driver, row.owner, row.next_review_date, row.provenance]))
  const actionHeadingRow = operating.rowCount + 2
  operating.addRow([])
  operating.addRow(['Action register · illustrative session-only actions'])
  operating.addRow(['Observation', 'Driver', 'Impact', 'Risk', 'Action', 'Owner', 'Due', 'Cadence', 'Status', 'Provenance'])
  sessionActions.forEach((action) => operating.addRow([action.observation, action.driver, nullableNumber(action.impact), action.risk, action.action, action.owner, action.due_period, action.cadence, action.status || 'Open', action.provenance]))
  const governanceHeadingRow = operating.rowCount + 2
  operating.addRow([])
  operating.addRow(['Governance metadata and decision evidence'])
  operating.addRow(['assumption_version', assumptionVersion, 'git_sha', gitSha, 'Case / as-of', dashboard.metadata.case_id, dashboard.metadata.as_of_date])
  operating.addRow(['Decision ID', 'Date', 'Context', 'Options', 'Decision', 'Rationale', 'Owner role', 'Affected contracts', 'Evidence', 'Supersedes', 'Status'])
  exportedDecisionLog.forEach((decision) => operating.addRow([decision.decision_id, decision.date, decision.context, Array.isArray(decision.options) ? decision.options.join(' | ') : decision.options, decision.decision, decision.rationale, decision.owner_role, Array.isArray(decision.affected_contracts) ? decision.affected_contracts.join(' | ') : decision.affected_contracts, Array.isArray(decision.evidence) ? decision.evidence.map((item) => `${item.metric}: ${item.formula} · ${item.source} · ${item.reconciliation_status}`).join(' | ') : decision.evidence, decision.supersedes, decision.status]))
  operating.addRow([])
  const reconciliation = operatingPlan?.reconciliation
  operating.addRow([
    'Reconciliation status', reconciliation?.status || 'Not available',
    'Cash bridge status', reconciliation?.cash_bridge.status || 'Not available',
    'Cash residual', nullableNumber(reconciliation?.cash_bridge.max_residual ?? null),
    'Category roll-up status', reconciliation?.category_rollup.status || 'Not available',
    'Category residual', nullableNumber(reconciliation?.category_rollup.revenue_residual ?? null),
    'Tolerance', nullableNumber(reconciliation?.tolerance_rmb_millions ?? null),
  ])
  configureSheet(operating, 6, [22, 26, 18, 18, 18, 18, 18, 18, 18, 18, 18, 28])
  const operatingNumericRows = Array.from({ length: workingCapitalRows.length }, (_, index) => 7 + index)
  formatColumns(operating, operatingNumericRows, [3, 4, 5, 6, 7, 8, 9, 10])
  formatColumns(operating, Array.from({ length: cashRows.length + 4 }, (_, index) => cashStartRow + index), [2])
  formatColumns(operating, accuracyRows.map((_, index) => accuracyHeadingRow + 2 + index), [2])
  operating.getRow(actionHeadingRow).font = { bold: true }
  operating.getRow(governanceHeadingRow).font = { bold: true }

  // Sanitize only primitive text cells; Excel formulas and numeric values remain untouched.
  sanitizeWorkbookText(workbook)

  const buffer = await workbook.xlsx.writeBuffer()
  saveAs(new Blob([buffer]), FILE_NAME)
  return FILE_NAME
}
