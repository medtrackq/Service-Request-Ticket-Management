import type { ReactNode } from 'react'
import type { FormFieldDef } from '../api/types'
import { cx } from '../components/ui'
import { useI18n } from '../i18n'
import { todayBangkok } from '../lib/dates'

const AUTOCOMPLETE: Record<string, string> = {
  organization: 'organization',
  contact_name: 'name',
  phone: 'tel',
  email: 'email',
}

interface Props {
  field: FormFieldDef
  value: string
  error?: string | null
  onChange: (v: string) => void
  onBlur?: () => void
}

export function DynamicField({ field: f, value, error, onChange, onBlur }: Props) {
  const { pick } = useI18n()
  const id = `f-${f.key}`
  const errId = `${id}-err`
  const helpId = `${id}-help`
  const label = pick(f, 'label')
  const placeholder = pick(f, 'placeholder') || undefined
  const help = pick(f, 'help')
  const rules = (f.validation ?? {}) as Record<string, unknown>
  const maxLen = typeof rules.max_length === 'number' ? rules.max_length : f.field_type === 'textarea' ? 5000 : 255
  const describedBy = [error ? errId : null, help ? helpId : null].filter(Boolean).join(' ') || undefined
  const common = {
    id,
    name: f.key,
    'aria-invalid': !!error,
    'aria-describedby': describedBy,
    'aria-required': f.required,
    className: cx('input', error && 'input-error'),
    onBlur,
  }

  let control: ReactNode
  if (f.field_type === 'textarea') {
    control = (
      <>
        <textarea {...common} rows={4} value={value} maxLength={maxLen} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
        {value.length > maxLen * 0.8 && (
          <p className="mt-1 text-right text-xs text-slate-500">
            {value.length}/{maxLen}
          </p>
        )}
      </>
    )
  } else if (f.field_type === 'select') {
    const opts = f.options ?? []
    if (opts.length <= 4) {
      control = (
        <div role="radiogroup" aria-labelledby={`${id}-label`} aria-describedby={describedBy} className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {opts.map((o) => {
            const checked = value === o.value
            return (
              <label
                key={o.value}
                className={cx(
                  'flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition',
                  checked ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-500/20' : 'border-slate-300 bg-white hover:border-slate-400',
                  error && !checked && 'border-red-300',
                )}
              >
                <input
                  type="radio"
                  name={f.key}
                  value={o.value}
                  checked={checked}
                  onChange={() => onChange(o.value)}
                  className="h-4 w-4 accent-brand-600"
                />
                <span className="text-slate-800">{pick(o, 'label')}</span>
              </label>
            )
          })}
        </div>
      )
    } else {
      control = (
        <select {...common} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">— {pick({ label_th: 'กรุณาเลือก', label_en: 'Please select' }, 'label')} —</option>
          {opts.map((o) => (
            <option key={o.value} value={o.value}>
              {pick(o, 'label')}
            </option>
          ))}
        </select>
      )
    }
  } else if (f.field_type === 'date') {
    const today = todayBangkok()
    control = (
      <input
        {...common}
        type="date"
        value={value}
        max={rules.not_future ? today : undefined}
        min={rules.not_past ? today : undefined}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  } else if (f.field_type === 'number') {
    control = (
      <input
        {...common}
        type="text"
        inputMode="numeric"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value.replace(/[^\d.,-]/g, ''))}
      />
    )
  } else {
    const type = f.field_type === 'email' ? 'email' : f.field_type === 'tel' ? 'tel' : 'text'
    control = (
      <input
        {...common}
        type={type}
        inputMode={f.field_type === 'tel' ? 'tel' : f.field_type === 'email' ? 'email' : undefined}
        autoComplete={AUTOCOMPLETE[f.key] ?? 'off'}
        value={value}
        maxLength={f.field_type === 'tel' ? 30 : maxLen}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  }

  return (
    <div data-field={f.key}>
      <label htmlFor={f.field_type === 'select' && (f.options?.length ?? 0) <= 4 ? undefined : id} id={`${id}-label`} className="label">
        {label}
        {f.required ? (
          <span className="ml-0.5 text-red-600" aria-hidden>
            *
          </span>
        ) : (
          <span className="ml-1 text-xs font-normal text-slate-400">({pick({ label_th: 'ไม่บังคับ', label_en: 'optional' }, 'label')})</span>
        )}
      </label>
      {control}
      {help && (
        <p id={helpId} className="mt-1 text-xs text-slate-500">
          {help}
        </p>
      )}
      {error && (
        <p id={errId} className="mt-1 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
