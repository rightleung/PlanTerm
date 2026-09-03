import { createContext, createElement, useContext, useMemo, useState, type ReactNode } from 'react'
import { en, type EnglishCatalog } from './locales/en'
import { zhCN } from './locales/zh-CN'
import { zhTW } from './locales/zh-TW'

export type Locale = 'en' | 'zh-CN' | 'zh-TW'
export const defaultLocale: Locale = 'en'
export const localeStorageKey = 'planterm.locale'
export type TranslationKey = keyof EnglishCatalog
export type TranslationCatalog = Partial<Record<TranslationKey, string>>
const catalogs: Record<Locale, Partial<TranslationCatalog>> = { en, 'zh-CN': zhCN, 'zh-TW': zhTW }
const languageNames: Record<Locale, string> = { en: 'English', 'zh-CN': '简体中文', 'zh-TW': '繁體中文' }
let missingKeyCount = 0
export function getMissingKeyCount() { return missingKeyCount }
export function isLocale(value: unknown): value is Locale { return value === 'en' || value === 'zh-CN' || value === 'zh-TW' }
export function detectLocale(storage: Storage | undefined = typeof window !== 'undefined' ? window.localStorage : undefined, language = typeof navigator !== 'undefined' ? navigator.language : ''): Locale {
  const stored = storage?.getItem(localeStorageKey)
  if (stored) { if (isLocale(stored)) return stored; storage?.removeItem(localeStorageKey) }
  if (language.toLowerCase().startsWith('zh-tw') || language.toLowerCase().startsWith('zh-hk') || language.toLowerCase().startsWith('zh-mo')) return 'zh-TW'
  if (language.toLowerCase().startsWith('zh')) return 'zh-CN'
  return defaultLocale
}
function interpolate(value: string, vars: Record<string, string | number> = {}) { return value.replace(/\{(\w+)\}/g, (_, key: string) => String(vars[key] ?? `{${key}}`)) }
export function translate(locale: Locale, key: TranslationKey, vars?: Record<string, string | number>): string {
  const value = catalogs[locale][key] ?? catalogs.en[key]
  if (value === undefined) { missingKeyCount += 1; if (import.meta.env?.DEV) console.warn(`[i18n] Missing translation key: ${String(key)}`); return String(key) }
  if (!catalogs[locale][key] && locale !== 'en') { missingKeyCount += 1; if (import.meta.env?.DEV) console.warn(`[i18n] Falling back to English for: ${String(key)}`) }
  return interpolate(value, vars)
}
export function formatNumber(value: number | null | undefined, locale: Locale, options: Intl.NumberFormatOptions = {}) { return value == null || !Number.isFinite(value) ? translate(locale, 'notAvailable') : new Intl.NumberFormat(locale, { maximumFractionDigits: 1, ...options }).format(value) }
export function formatCurrency(value: number | null | undefined, locale: Locale, currency = 'CNY', scale: 'native' | 'thousands' | 'millions' = 'millions') { if (value == null || !Number.isFinite(value)) return translate(locale, 'notAvailable'); const suffix = scale === 'millions' ? 'm' : scale === 'thousands' ? 'k' : ''; return `${new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: 1 }).format(value)}${suffix}` }
export function formatDate(value: string | Date | null | undefined, locale: Locale) { if (!value) return translate(locale, 'notAvailable'); const date = value instanceof Date ? value : new Date(`${value}T00:00:00Z`); return Number.isNaN(date.getTime()) ? translate(locale, 'notAvailable') : new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' }).format(date) }
export function formatPlural(value: number, locale: Locale, singular: string, plural: string) { return new Intl.PluralRules(locale).select(value) === 'one' ? singular : plural }
type I18nContext = { locale: Locale; setLocale: (locale: Locale) => void; t: (key: TranslationKey, vars?: Record<string, string | number>) => string; formatNumber: (value: number | null | undefined, options?: Intl.NumberFormatOptions) => string; formatCurrency: (value: number | null | undefined, currency?: string, scale?: 'native' | 'thousands' | 'millions') => string; formatDate: (value: string | Date | null | undefined) => string; formatPlural: (value: number, singular: string, plural: string) => string }
const Context = createContext<I18nContext | null>(null)
export function I18nProvider({ children }: { children: ReactNode }) { const [locale, setLocaleState] = useState<Locale>(() => detectLocale()); const setLocale = (next: Locale) => { setLocaleState(next); if (typeof window !== 'undefined') window.localStorage.setItem(localeStorageKey, next) }; const value = useMemo<I18nContext>(() => ({ locale, setLocale, t: (key, vars) => translate(locale, key, vars), formatNumber: (v, o) => formatNumber(v, locale, o), formatCurrency: (v, c, s) => formatCurrency(v, locale, c, s), formatDate: (v) => formatDate(v, locale), formatPlural: (v, s, p) => formatPlural(v, locale, s, p) }), [locale]); return createElement(Context.Provider, { value }, children) }
export function useI18n() { const value = useContext(Context); if (!value) throw new Error('useI18n must be used within I18nProvider'); return value }
export function localeName(locale: Locale) { return languageNames[locale] }
export const localeCatalogs = catalogs
