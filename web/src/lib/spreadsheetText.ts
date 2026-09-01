export const SPREADSHEET_TRIGGER_CHARACTERS = new Set(['=', '+', '-', '@'])
const NUMERIC_TEXT_PATTERN = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/

export function neutralizeSpreadsheetText(value: string): string {
  if (value.length === 0 || value.startsWith("'") || !SPREADSHEET_TRIGGER_CHARACTERS.has(value[0])) return value
  return `'${value}`
}

export function numericSpreadsheetValue(value: number | string, field: string): number {
  if (typeof value === 'string' && !NUMERIC_TEXT_PATTERN.test(value.trim())) throw new Error(`Invalid numeric value for ${field}`)
  const parsed = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(parsed)) throw new Error(`Invalid numeric value for ${field}`)
  return parsed
}

export function sanitizeSpreadsheetCell(value: unknown): unknown {
  return typeof value === 'string' ? neutralizeSpreadsheetText(value) : value
}
