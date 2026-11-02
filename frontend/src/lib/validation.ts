// Client-side validation mirroring backend/app/services/form_engine.py (UX only — the server is authoritative).
import type { FormFieldDef, Lang } from '../api/types'
import { todayBangkok } from './dates'

const PHONE_ALLOWED = /^[0-9+\-()\s.,#/a-zA-Zก-๙]*$/
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

function msg(lang: Lang, th: string, en: string) {
  return lang === 'en' ? en : th
}

export function isEmpty(v: unknown): boolean {
  return v === undefined || v === null || (typeof v === 'string' && v.trim() === '')
}

export function validateField(f: FormFieldDef, raw: unknown, lang: Lang): string | null {
  const rules = (f.validation ?? {}) as Record<string, unknown>
  if (f.field_type === 'file') return null
  if (isEmpty(raw)) {
    if (!f.required) return null
    return f.field_type === 'select'
      ? msg(lang, 'กรุณาเลือกข้อมูลนี้', 'Please select an option')
      : msg(lang, 'กรุณากรอกข้อมูลนี้', 'This field is required')
  }
  const value = String(raw).trim()
  switch (f.field_type) {
    case 'text':
    case 'textarea': {
      const max = Number(rules.max_length ?? (f.field_type === 'textarea' ? 5000 : 255))
      if (value.length > max) return msg(lang, `ความยาวต้องไม่เกิน ${max} ตัวอักษร`, `Maximum ${max} characters`)
      const min = Number(rules.min_length ?? 0)
      if (value.length < min) return msg(lang, `กรุณากรอกอย่างน้อย ${min} ตัวอักษร`, `At least ${min} characters`)
      if (typeof rules.pattern === 'string' && !new RegExp(`^(?:${rules.pattern})$`).test(value))
        return msg(lang, 'รูปแบบข้อมูลไม่ถูกต้อง', 'Invalid format')
      return null
    }
    case 'email':
      return EMAIL_RE.test(value) ? null : msg(lang, 'รูปแบบอีเมลไม่ถูกต้อง', 'Invalid email address')
    case 'tel': {
      const digits = value.replace(/\D/g, '')
      if (value.length > 30 || !PHONE_ALLOWED.test(value) || digits.length < 9 || digits.length > 20)
        return msg(lang, 'รูปแบบเบอร์โทรศัพท์ไม่ถูกต้อง', 'Invalid telephone number')
      return null
    }
    case 'number': {
      const n = Number(value.replace(/,/g, ''))
      if (!Number.isFinite(n)) return msg(lang, 'ต้องเป็นตัวเลข', 'Must be a number')
      if (rules.integer !== false && !Number.isInteger(n)) return msg(lang, 'ต้องเป็นจำนวนเต็ม', 'Must be a whole number')
      if (typeof rules.min === 'number' && n < rules.min) return msg(lang, `ต้องไม่น้อยกว่า ${rules.min}`, `Minimum ${rules.min}`)
      if (typeof rules.max === 'number' && n > rules.max) return msg(lang, `ต้องไม่เกิน ${rules.max}`, `Maximum ${rules.max}`)
      return null
    }
    case 'date': {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(new Date(value).getTime()))
        return msg(lang, 'รูปแบบวันที่ไม่ถูกต้อง', 'Invalid date')
      const year = Number(value.slice(0, 4))
      if (year < 2000 || year > 2100) return msg(lang, 'วันที่ไม่ถูกต้อง', 'Invalid date')
      const today = todayBangkok()
      if (rules.not_future && value > today) return msg(lang, 'วันที่ต้องไม่เป็นวันในอนาคต', 'Date cannot be in the future')
      if (rules.not_past && value < today) return msg(lang, 'วันที่ต้องไม่เป็นวันที่ผ่านมาแล้ว', 'Date cannot be in the past')
      return null
    }
    case 'select':
      return (f.options ?? []).some((o) => o.value === value) ? null : msg(lang, 'กรุณาเลือกจากรายการที่กำหนด', 'Please choose from the list')
    default:
      return null
  }
}

/** Normalise a raw input value before sending it to the API. */
export function normaliseValue(f: FormFieldDef, raw: unknown): unknown {
  if (isEmpty(raw)) return null
  const s = String(raw).trim()
  if (f.field_type === 'number') {
    const n = Number(s.replace(/,/g, ''))
    return Number.isFinite(n) ? n : s
  }
  return s
}
