import type { Lang } from '../api/types'

export const TIMEZONE = 'Asia/Bangkok'

function locale(lang: Lang) {
  return lang === 'th' ? 'th-TH' : 'en-GB'
}

export function formatDateTime(iso: string | null | undefined, lang: Lang = 'th'): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '-'
  return new Intl.DateTimeFormat(locale(lang), {
    timeZone: TIMEZONE,
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

export function formatDate(iso: string | null | undefined, lang: Lang = 'th'): string {
  if (!iso) return '-'
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00+07:00` : iso)
  if (Number.isNaN(d.getTime())) return '-'
  return new Intl.DateTimeFormat(locale(lang), { timeZone: TIMEZONE, day: 'numeric', month: 'short', year: 'numeric' }).format(d)
}

export function formatMonth(ym: string, lang: Lang = 'th'): string {
  const [y, m] = ym.split('-').map(Number)
  if (!y || !m) return ym
  const d = new Date(Date.UTC(y, m - 1, 15))
  return new Intl.DateTimeFormat(locale(lang), { timeZone: TIMEZONE, month: 'short', year: '2-digit' }).format(d)
}

/** Today's date in Bangkok as YYYY-MM-DD. */
export function todayBangkok(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: TIMEZONE, year: 'numeric', month: '2-digit', day: '2-digit' }).format(
    new Date(),
  )
}

/** ISO instant -> value for <input type="datetime-local"> in Bangkok time. */
export function toBangkokLocalInput(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(d)
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '00'
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`
}

/** <input type="datetime-local"> value interpreted as Bangkok time (UTC+7, no DST) -> ISO string. */
export function fromBangkokLocalInput(value: string): string | null {
  if (!value) return null
  return `${value.length === 16 ? `${value}:00` : value}+07:00`
}

export function hoursLabel(h: number | null | undefined, lang: Lang): string {
  if (h == null) return '-'
  if (h < 48) return lang === 'th' ? `${h.toFixed(1)} ชม.` : `${h.toFixed(1)} h`
  const days = h / 24
  return lang === 'th' ? `${days.toFixed(1)} วัน` : `${days.toFixed(1)} d`
}
