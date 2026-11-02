/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Lang } from '../api/types'

const STORAGE_KEY = 'buc.lang'

function readStoredLang(): Lang {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY)
    return v === 'en' ? 'en' : 'th'
  } catch {
    return 'th'
  }
}

interface I18nValue {
  lang: Lang
  setLang: (l: Lang) => void
  /** Inline translation: tr('ภาษาไทย', 'English') */
  tr: (th: string, en: string) => string
  /** Pick a localised attribute, e.g. pick(obj, 'name') -> obj.name_th | obj.name_en */
  pick: (obj: object | null | undefined, base: string) => string
}

const I18nContext = createContext<I18nValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readStoredLang)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try {
      window.localStorage.setItem(STORAGE_KEY, l)
    } catch {
      /* storage unavailable (private mode / in-app browser) */
    }
  }, [])

  const value = useMemo<I18nValue>(
    () => ({
      lang,
      setLang,
      tr: (th, en) => (lang === 'en' ? en : th),
      pick: (obj, base) => {
        if (!obj) return ''
        const rec = obj as Record<string, unknown>
        const v = rec[`${base}_${lang}`] ?? rec[`${base}_th`] ?? rec[base]
        return v == null ? '' : String(v)
      },
    }),
    [lang, setLang],
  )
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used inside I18nProvider')
  return ctx
}

export const PRIORITY_LABELS: Record<string, { th: string; en: string }> = {
  LOW: { th: 'ต่ำ', en: 'Low' },
  NORMAL: { th: 'ปกติ', en: 'Normal' },
  HIGH: { th: 'สูง', en: 'High' },
  URGENT: { th: 'เร่งด่วน', en: 'Urgent' },
}

export const ROLE_LABELS: Record<string, { th: string; en: string }> = {
  ADMIN: { th: 'ผู้ดูแลระบบ', en: 'System Administrator' },
  MANAGER: { th: 'ผู้จัดการแผนก', en: 'Department Manager' },
  STAFF: { th: 'เจ้าหน้าที่', en: 'Staff' },
}

export const CUSTOMER_TYPE_LABELS: Record<string, { th: string; en: string }> = {
  GOV_HOSPITAL: { th: 'โรงพยาบาลรัฐ', en: 'Government hospital' },
  PRIVATE_HOSPITAL: { th: 'โรงพยาบาลเอกชน', en: 'Private hospital' },
  CLINIC: { th: 'คลินิก', en: 'Clinic' },
  COMPANY: { th: 'บริษัท / ห้างร้าน', en: 'Company' },
  OTHER: { th: 'อื่น ๆ', en: 'Other' },
}

export function label(map: Record<string, { th: string; en: string }>, key: string | null | undefined, lang: Lang) {
  if (!key) return ''
  return map[key]?.[lang] ?? key
}
