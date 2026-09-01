import type { BrandFilter, DashboardResponse, ForecastAccuracy, MarketFilter, OperatingPlanPreviewRequest, OperatingPlanResponse, PlanVariant, PlanningInputRow } from '@/types/planning'

export class ApiError extends Error {
  status: number
  errorType: string
  details: Record<string, unknown>

  constructor(message: string, status: number, errorType = 'request_error', details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.errorType = errorType
    this.details = details
  }
}

export async function fetchDashboard(caseId: string, brand: BrandFilter, market: MarketFilter, signal?: AbortSignal, selectedPlanVariant?: PlanVariant): Promise<DashboardResponse> {
  const params = new URLSearchParams({ brand, market })
  if (selectedPlanVariant) params.set('plan_variant', selectedPlanVariant)
  const response = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/dashboard?${params}`, { signal })
  const body = await response.json().catch(() => null) as { error?: string; error_type?: string; details?: Record<string, unknown> } | null
  if (!response.ok) {
    throw new ApiError(body?.error || `Request failed (${response.status})`, response.status, body?.error_type, body?.details)
  }
  return body as DashboardResponse
}

async function parseApiResponse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null) as { error?: string; error_type?: string; details?: Record<string, unknown> } | null
  if (!response.ok) throw new ApiError(body?.error || `Request failed (${response.status})`, response.status, body?.error_type, body?.details)
  return body as T
}

export async function fetchPlanningTemplate(caseId: string, signal?: AbortSignal): Promise<string> {
  const response = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/planning-input-template`, { signal, headers: { Accept: 'text/csv' } })
  if (!response.ok) return parseApiResponse<never>(response)
  return response.text()
}

function finiteDriver(value: unknown, field: string): number {
  const number = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(number)) throw new ApiError(`Import returned a non-finite ${field}`, 502, 'invalid_import_response')
  return number
}

function normalizeRows(rows: PlanningInputRow[]): PlanningInputRow[] {
  return rows.map((row) => ({ ...row,
    volume_change_pct: finiteDriver(row.volume_change_pct, 'volume_change_pct'),
    average_ticket_change_pct: finiteDriver(row.average_ticket_change_pct, 'average_ticket_change_pct'),
    gross_margin_delta_pp: finiteDriver(row.gross_margin_delta_pp, 'gross_margin_delta_pp'),
    opex_ratio_delta_pp: finiteDriver(row.opex_ratio_delta_pp, 'opex_ratio_delta_pp'),
  }))
}

export async function importPlanningInputs(caseId: string, csv: string, signal?: AbortSignal) {
  const response = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/planning-inputs/import`, { method: 'POST', body: csv, signal, headers: { 'Content-Type': 'text/csv' } })
  const result = await parseApiResponse<{ rows: PlanningInputRow[]; row_count: number; validated: boolean }>(response)
  return { ...result, rows: normalizeRows(result.rows) }
}

export async function previewDashboard(caseId: string, rows: PlanningInputRow[], selectedPlanVariant: PlanVariant, planningInputSource: 'upload' | 'editor', brand: BrandFilter = 'all', market: MarketFilter = 'all', signal?: AbortSignal): Promise<DashboardResponse> {
  const response = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/dashboard/preview?brand=${encodeURIComponent(brand)}&market=${encodeURIComponent(market)}`, { method: 'POST', body: JSON.stringify({ rows: normalizeRows(rows), selected_plan_variant: selectedPlanVariant, planning_input_source: planningInputSource }), signal, headers: { 'Content-Type': 'application/json' } })
  return parseApiResponse<DashboardResponse>(response)
}

export async function fetchOperatingPlan(caseId: string, planVariant: PlanVariant = 'base', signal?: AbortSignal): Promise<OperatingPlanResponse> {
  const params = new URLSearchParams({ plan_variant: planVariant })
  const response = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/operating-plan?${params}`, { signal })
  return parseApiResponse<OperatingPlanResponse>(response)
}

export async function previewOperatingPlan(caseId: string, request: OperatingPlanPreviewRequest, signal?: AbortSignal): Promise<OperatingPlanResponse> {
  const response = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/operating-plan/preview`, {
    method: 'POST',
    body: JSON.stringify({ ...request, case_id: caseId, rows: normalizeRows(request.rows) }),
    signal,
    headers: { 'Content-Type': 'application/json' },
  })
  return parseApiResponse<OperatingPlanResponse>(response)
}

export async function fetchForecastAccuracy(caseId: string, signal?: AbortSignal): Promise<ForecastAccuracy> {
  const response = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/forecast-accuracy`, { signal })
  return parseApiResponse<ForecastAccuracy>(response)
}
