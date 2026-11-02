import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useI18n, PRIORITY_LABELS } from '../i18n'
import { IconCheck, IconCopy, IconX } from './Icons'

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(' ')
}

// Static class map so Tailwind can see every class (status colours come from the API).
const COLOR_CLASSES: Record<string, string> = {
  blue: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  indigo: 'bg-indigo-50 text-indigo-700 ring-indigo-600/20',
  violet: 'bg-violet-50 text-violet-700 ring-violet-600/20',
  amber: 'bg-amber-50 text-amber-800 ring-amber-600/25',
  orange: 'bg-orange-50 text-orange-700 ring-orange-600/25',
  yellow: 'bg-yellow-50 text-yellow-800 ring-yellow-600/30',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/25',
  slate: 'bg-slate-100 text-slate-700 ring-slate-500/25',
  gray: 'bg-slate-100 text-slate-700 ring-slate-500/25',
  red: 'bg-red-50 text-red-700 ring-red-600/20',
}

export const COLOR_HEX: Record<string, string> = {
  blue: '#2563eb',
  indigo: '#4f46e5',
  violet: '#7c3aed',
  amber: '#d97706',
  orange: '#ea580c',
  yellow: '#ca8a04',
  green: '#059669',
  slate: '#64748b',
  gray: '#64748b',
  red: '#dc2626',
}

export function Badge({ color = 'gray', children, className }: { color?: string; children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset',
        COLOR_CLASSES[color] ?? COLOR_CLASSES.gray,
        className,
      )}
    >
      {children}
    </span>
  )
}

export function StatusBadge({ status }: { status: { code?: string; name_th: string; name_en: string; color?: string } }) {
  const { pick } = useI18n()
  return <Badge color={status.color ?? 'gray'}>{pick(status, 'name')}</Badge>
}

const PRIORITY_COLOR: Record<string, string> = { LOW: 'slate', NORMAL: 'blue', HIGH: 'orange', URGENT: 'red' }

export function PriorityBadge({ priority }: { priority: string }) {
  const { lang } = useI18n()
  return (
    <Badge color={PRIORITY_COLOR[priority] ?? 'gray'}>
      {priority === 'URGENT' && <span aria-hidden>●</span>}
      {PRIORITY_LABELS[priority]?.[lang] ?? priority}
    </Badge>
  )
}

export function SampleBadge() {
  const { tr } = useI18n()
  return (
    <Badge color="yellow" className="uppercase">
      {tr('ตัวอย่าง', 'Sample')}
    </Badge>
  )
}

export function Spinner({ className = 'h-5 w-5' }: { className?: string }) {
  return (
    <svg className={cx('animate-spin text-current', className)} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  )
}

export function Loading({ label }: { label?: string }) {
  const { tr } = useI18n()
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-slate-500" role="status">
      <Spinner />
      <span>{label ?? tr('กำลังโหลด...', 'Loading...')}</span>
    </div>
  )
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { tr } = useI18n()
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn-secondary mt-3" onClick={onRetry}>
          {tr('ลองใหม่', 'Try again')}
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-14 text-center text-slate-500">
      <div className="rounded-full bg-slate-100 p-3 text-slate-400">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
          <path d="M3 7h18l-2 13H5L3 7ZM8 7V5a4 4 0 0 1 8 0v2" />
        </svg>
      </div>
      <p className="font-medium text-slate-700">{title}</p>
      {children}
    </div>
  )
}

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  wide,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    ref.current?.querySelector<HTMLElement>('input,select,textarea,button')?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-navy-950/50 p-0 sm:items-center sm:p-4" onMouseDown={onClose}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cx(
          'flex max-h-[92vh] w-full flex-col rounded-t-2xl bg-white shadow-xl sm:rounded-2xl',
          wide ? 'sm:max-w-3xl' : 'sm:max-w-lg',
        )}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
          <h2 className="text-base font-semibold text-navy-900">{title}</h2>
          <button type="button" className="rounded-md p-1 text-slate-500 hover:bg-slate-100" onClick={onClose} aria-label="close">
            <IconX />
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  danger,
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  message: ReactNode
  confirmLabel?: string
  danger?: boolean
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const { tr } = useI18n()
  return (
    <Modal
      open={open}
      title={title}
      onClose={onCancel}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onCancel}>
            {tr('ยกเลิก', 'Cancel')}
          </button>
          <button type="button" className={danger ? 'btn-danger' : 'btn-primary'} onClick={onConfirm} disabled={busy}>
            {busy && <Spinner className="h-4 w-4" />}
            {confirmLabel ?? tr('ยืนยัน', 'Confirm')}
          </button>
        </>
      }
    >
      <div className="text-sm text-slate-700">{message}</div>
    </Modal>
  )
}

export function CopyButton({ text, label, className }: { text: string; label?: string; className?: string }) {
  const { tr } = useI18n()
  const [done, setDone] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      try {
        document.execCommand('copy')
      } catch {
        /* ignore */
      }
      ta.remove()
    }
    setDone(true)
    setTimeout(() => setDone(false), 1800)
  }
  return (
    <button type="button" onClick={copy} className={cx('btn-secondary', className)}>
      {done ? <IconCheck size={16} /> : <IconCopy size={16} />}
      {done ? tr('คัดลอกแล้ว', 'Copied') : (label ?? tr('คัดลอก', 'Copy'))}
    </button>
  )
}

export function FieldError({ message, id }: { message?: string | null; id?: string }) {
  if (!message) return null
  return (
    <p id={id} className="mt-1 text-sm text-red-600" role="alert">
      {message}
    </p>
  )
}

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number
  pageSize: number
  total: number
  onPage: (p: number) => void
}) {
  const { tr } = useI18n()
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(total, page * pageSize)
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-3 text-sm text-slate-600">
      <span>
        {tr(`แสดง ${from}-${to} จาก ${total} รายการ`, `Showing ${from}-${to} of ${total}`)}
      </span>
      <div className="flex items-center gap-1">
        <button type="button" className="btn-secondary px-3 py-1.5" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          {tr('ก่อนหน้า', 'Prev')}
        </button>
        <span className="px-2">
          {page} / {pages}
        </span>
        <button type="button" className="btn-secondary px-3 py-1.5" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          {tr('ถัดไป', 'Next')}
        </button>
      </div>
    </div>
  )
}

export function SectionCard({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx('card', className)}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
          {title && <h2 className="text-sm font-semibold text-navy-900">{title}</h2>}
          {actions}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label?: string; disabled?: boolean }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx(
          'relative h-6 w-11 shrink-0 rounded-full transition disabled:opacity-50',
          checked ? 'bg-brand-600' : 'bg-slate-300',
        )}
      >
        <span className={cx('absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition', checked && 'translate-x-5')} />
      </button>
      {label && <span className="text-sm text-slate-700">{label}</span>}
    </label>
  )
}

export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] gap-2 py-1.5 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="break-words text-slate-800">{children ?? '-'}</dd>
    </div>
  )
}
