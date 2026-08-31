import type { BrandFilter, DashboardResponse, MarketFilter } from '@/types/planning'

export class ApiError extends Error {
  status: number
  errorType: string

  constructor(message: string, status: number, errorType = 'request_error') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.errorType = errorType
  }
}

export async function fetchDashboard(caseId: string, brand: BrandFilter, market: MarketFilter): Promise<DashboardResponse> {
  const params = new URLSearchParams({ brand, market })
  const response = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/dashboard?${params}`)
  const body = await response.json().catch(() => null) as { error?: string; error_type?: string } | null
  if (!response.ok) {
    throw new ApiError(body?.error || `Request failed (${response.status})`, response.status, body?.error_type)
  }
  return body as DashboardResponse
}
