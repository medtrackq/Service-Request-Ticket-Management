import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { NotificationItem, Page } from '../api/types'
import { IconBell } from '../components/Icons'
import { Spinner, cx } from '../components/ui'
import { useI18n } from '../i18n'
import { formatDateTime } from '../lib/dates'

const POLL_MS = 60_000

export function NotificationBell() {
  const { tr, lang } = useI18n()
  const navigate = useNavigate()
  const [count, setCount] = useState(0)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[] | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  const poll = useCallback(() => {
    api
      .get<{ count: number }>('/notifications/unread-count')
      .then((r) => setCount(r.count))
      .catch(() => {})
  }, [])

  useEffect(() => {
    poll()
    const id = window.setInterval(() => document.visibilityState === 'visible' && poll(), POLL_MS)
    return () => window.clearInterval(id)
  }, [poll])

  useEffect(() => {
    if (!open) return
    setItems(null)
    api
      .get<Page<NotificationItem>>('/notifications?page_size=8')
      .then((r) => setItems(r.items))
      .catch(() => setItems([]))
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  async function openItem(n: NotificationItem) {
    if (!n.read_at) {
      await api.post(`/notifications/${n.id}/read`).catch(() => {})
      poll()
    }
    setOpen(false)
    if (n.ticket_id) navigate(`/admin/tickets/${n.ticket_id}`)
  }

  async function readAll() {
    await api.post('/notifications/read-all').catch(() => {})
    setItems((xs) => xs?.map((x) => ({ ...x, read_at: x.read_at ?? new Date().toISOString() })) ?? null)
    setCount(0)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="relative rounded-full p-2 text-slate-600 hover:bg-slate-100"
        aria-label={tr(`การแจ้งเตือน ${count} รายการที่ยังไม่อ่าน`, `${count} unread notifications`)}
        aria-expanded={open}
      >
        <IconBell />
        {count > 0 && (
          <span className="absolute top-0.5 right-0.5 grid h-5 min-w-5 place-items-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-[min(92vw,380px)] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
            <p className="text-sm font-semibold text-navy-900">{tr('การแจ้งเตือน', 'Notifications')}</p>
            <button type="button" className="text-xs font-medium text-brand-700 hover:underline" onClick={readAll}>
              {tr('อ่านทั้งหมดแล้ว', 'Mark all read')}
            </button>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items === null ? (
              <div className="flex justify-center py-6 text-slate-400">
                <Spinner />
              </div>
            ) : items.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-slate-500">{tr('ไม่มีการแจ้งเตือน', 'No notifications')}</p>
            ) : (
              items.map((n) => (
                <button
                  type="button"
                  key={n.id}
                  onClick={() => openItem(n)}
                  className={cx('block w-full border-b border-slate-50 px-4 py-2.5 text-left hover:bg-slate-50', !n.read_at && 'bg-brand-50/60')}
                >
                  <p className={cx('text-sm', !n.read_at ? 'font-semibold text-navy-900' : 'text-slate-700')}>{n.subject}</p>
                  <p className="mt-0.5 text-xs text-slate-500">{formatDateTime(n.created_at, lang)}</p>
                </button>
              ))
            )}
          </div>
          <Link to="/admin/notifications" onClick={() => setOpen(false)} className="block bg-slate-50 px-4 py-2 text-center text-xs font-medium text-brand-700 hover:underline">
            {tr('ดูทั้งหมด', 'View all')}
          </Link>
        </div>
      )}
    </div>
  )
}
