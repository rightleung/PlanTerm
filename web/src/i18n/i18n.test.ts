import { beforeEach, describe, expect, it, vi } from 'vitest'
import { detectLocale, formatCurrency, formatDate, formatNumber, formatPlural, localeCatalogs, translate, type TranslationKey } from './index'
import { en } from './locales/en'
import { apiLabel } from './apiLabels'

describe('typed locale catalogs', () => {
  it('keeps English complete and exposes all locale catalogs', () => {
    expect(Object.keys(en).length).toBeGreaterThan(80)
    expect(Object.keys(localeCatalogs)).toEqual(expect.arrayContaining(['en', 'zh-CN', 'zh-TW']))
    expect(Object.keys(localeCatalogs['zh-TW'])).toEqual(Object.keys(en))
  })
  it('falls back to English and warns for missing non-English keys', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    expect(translate('zh-CN', 'missingTestKey' as TranslationKey)).toBe('missingTestKey')
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })
  it('localizes stable case labels without translating unknown data', () => {
    const t = (key: TranslationKey, vars?: Record<string, string | number>) => translate('zh-CN', key, vars)
    expect(apiLabel('MINISO - Overseas', t)).toBe('MINISO - 海外')
    expect(apiLabel('IP & Toys', t)).toBe('IP 与玩具')
    expect(apiLabel('store operations', t)).toBe('门店运营')
    expect(apiLabel('Approved', t)).toBe('已批准')
    expect(apiLabel('decision_table', t)).toBe('情景决策表')
    expect(apiLabel('provider-specific label', t)).toBe('provider-specific label')
  })
})

describe('locale detection and formatting', () => {
  const storage = { value: null as string | null, getItem: () => storage.value, setItem: (_key: string, value: string) => { storage.value = value }, removeItem: () => { storage.value = null } } as unknown as Storage
  beforeEach(() => storage.removeItem('planterm.locale'))
  it('prefers valid persisted locale and removes invalid values', () => {
    storage.setItem('planterm.locale', 'zh-TW')
    expect(detectLocale(storage, 'en-US')).toBe('zh-TW')
    storage.setItem('planterm.locale', 'fr-FR')
    expect(detectLocale(storage, 'zh-CN')).toBe('zh-CN')
    expect(storage.getItem('planterm.locale')).toBeNull()
  })
  it('maps browser Chinese locales', () => {
    expect(detectLocale(undefined, 'zh-TW')).toBe('zh-TW')
    expect(detectLocale(undefined, 'zh-CN')).toBe('zh-CN')
    expect(detectLocale(undefined, 'en-US')).toBe('en')
  })
  it('formats numbers, currencies, dates and plurals with Intl', () => {
    expect(formatNumber(1234.56, 'en')).toBe('1,234.6')
    expect(formatNumber(1234.56, 'zh-CN')).toContain('1,234.6')
    expect(formatCurrency(12.5, 'en', 'CNY', 'millions')).toContain('CN¥12.5')
    expect(formatDate('2026-06-30', 'en')).toContain('Jun')
    expect(formatPlural(1, 'en', 'row', 'rows')).toBe('row')
    expect(formatPlural(2, 'zh-CN', 'row', 'rows')).toBe('rows')
  })
})
