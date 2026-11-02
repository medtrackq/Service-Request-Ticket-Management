import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, queryString } from '../api/client'
import type { NotificationItem, Page } from '../api/types'
import { EmptyState, ErrorBox, Loading, Pagination, Toggle, cx } from '../components/ui'
import { useI18n } from '../i18n'
import { formatDateTime } from '../lib/dates'
import { PageHeader } from './AdminLayout'
import { useApi } from './useApi'

export function NotificationsPage() {
  const { tr, lang } = useI18n()
  const [page, setPage] = useState(1)
  const [unread, setUnread] = useState(false)
  const { data, error, loading, reload } = useApi<Page<NotificationItem>>(`/notifications${queryString({ page, page_size: 20, unread_only: unread || undefined })}`)

  return (
    <div className="space-y-4">
      <PageHeader
        title={tr('การแจ้งเตือน', 'Notifications')}
        actions={
          <>
            <Toggle checked={unread} onChange={(v) => { setUnread(v); setPage(1) }} label={tr('เฉพาะที่ยังไม่อ่าน', 'Unread only')} />
            <button type="button" className="btn-secondary" onClick={() => api.post('/notifications/read-all').then(reload)}>
              {tr('อ่านทั้งหมดแล้ว', 'Mark all read')}
            </button>
          </>
        }
      />
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      <div className="card overflow-hidden">
        {!data && loading ? (
          <Loading />
        ) : !data || data.items.length === 0 ? (
          <EmptyState title={tr('ไม่มีการแจ้งเตือน', 'No notifications')} />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.items.map((n) => (
              <li key={n.id} className={cx('px-4 py-3', !n.read_at && 'bg-brand-50/50')}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className={cx('text-sm', !n.read_at ? 'font-semibold text-navy-900' : 'text-slate-700')}>{n.subject}</p>
                    <p className="mt-1 line-clamp-3 text-xs whitespace-pre-line text-slate-500">{n.body}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
                    {formatDateTime(n.created_at, lang)}
                    {n.ticket_id && (
                      <Link
                        to={`/admin/tickets/${n.ticket_id}`}
                        onClick={() => !n.read_at && api.post(`/notifications/${n.id}/read`).catch(() => {})}
                        className="btn-secondary px-2.5 py-1 text-xs"
                      >
                        {n.ticket_number ?? tr('เปิด', 'Open')}
                      </Link>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        {data && data.total > 0 && <Pagination page={page} pageSize={20} total={data.total} onPage={setPage} />}
      </div>
    </div>
  )
}
