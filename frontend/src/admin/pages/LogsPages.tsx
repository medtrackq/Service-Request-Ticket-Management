import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api, queryString } from '../../api/client'
import { useToast } from '../../components/Toast'
import { Badge, EmptyState, ErrorBox, Loading, Pagination } from '../../components/ui'
import { useI18n } from '../../i18n'
import { formatDateTime } from '../../lib/dates'
import { PageHeader } from '../AdminLayout'
import { useApi } from '../useApi'

interface AuditItem {
  id: number
  created_at: string
  actor_name: string | null
  actor_type: string
  action: string
  entity_type: string | null
  entity_id: string | null
  ip_address: string | null
  details: Record<string, unknown> | null
}

export function AuditLogsPage() {
  const { tr, lang } = useI18n()
  const [f, setF] = useState({ action: '', entity_type: '', entity_id: '', date_from: '', date_to: '' })
  const [applied, setApplied] = useState(f)
  const [page, setPage] = useState(1)
  const { data, error, loading, reload } = useApi<{ total: number; items: AuditItem[] }>(`/admin/audit-logs${queryString({ ...applied, page, page_size: 50 })}`)
  return (
    <div className="space-y-4">
      <PageHeader title="Audit Log" subtitle={tr('บันทึกการใช้งานด้านความปลอดภัยและการดำเนินงาน', 'Security and operational audit trail')} />
      <form
        className="card grid grid-cols-2 gap-3 p-3 md:grid-cols-6"
        onSubmit={(e) => {
          e.preventDefault()
          setPage(1)
          setApplied(f)
        }}
      >
        <input className="input py-2 text-sm" placeholder="action (e.g. ticket., auth.)" value={f.action} onChange={(e) => setF({ ...f, action: e.target.value })} />
        <input className="input py-2 text-sm" placeholder="entity_type" value={f.entity_type} onChange={(e) => setF({ ...f, entity_type: e.target.value })} />
        <input className="input py-2 text-sm" placeholder="entity_id" value={f.entity_id} onChange={(e) => setF({ ...f, entity_id: e.target.value })} />
        <input type="date" className="input py-2 text-sm" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} aria-label="from" />
        <input type="date" className="input py-2 text-sm" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} aria-label="to" />
        <button type="submit" className="btn-primary">
          {tr('กรอง', 'Filter')}
        </button>
      </form>
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      <div className="card overflow-x-auto">
        {!data && loading ? (
          <Loading />
        ) : !data?.items.length ? (
          <EmptyState title={tr('ไม่พบรายการ', 'No entries')} />
        ) : (
          <table className="table-base">
            <thead>
              <tr>
                <th>{tr('เวลา', 'Time')}</th>
                <th>{tr('ผู้กระทำ', 'Actor')}</th>
                <th>Action</th>
                <th>Entity</th>
                <th>IP</th>
                <th>{tr('รายละเอียด', 'Details')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((a) => (
                <tr key={a.id}>
                  <td className="text-xs whitespace-nowrap">{formatDateTime(a.created_at, lang)}</td>
                  <td className="text-xs">
                    {a.actor_name ?? '-'}
                    <p className="text-slate-400">{a.actor_type}</p>
                  </td>
                  <td className="font-mono text-xs">{a.action}</td>
                  <td className="text-xs whitespace-nowrap">
                    {a.entity_type === 'ticket' && a.entity_id ? (
                      <Link className="text-brand-700 hover:underline" to={`/admin/tickets/${a.entity_id}`}>
                        ticket #{a.entity_id}
                      </Link>
                    ) : (
                      `${a.entity_type ?? ''} ${a.entity_id ?? ''}`
                    )}
                  </td>
                  <td className="font-mono text-xs">{a.ip_address ?? '-'}</td>
                  <td className="max-w-md">
                    {a.details && <pre className="max-h-24 overflow-auto rounded bg-slate-50 p-1.5 text-[11px] whitespace-pre-wrap">{JSON.stringify(a.details, null, 1)}</pre>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data && data.total > 0 && <Pagination page={page} pageSize={50} total={data.total} onPage={setPage} />}
      </div>
    </div>
  )
}

interface NotifLog {
  id: number
  created_at: string
  ticket_id: number | null
  ticket_number: string | null
  event_type: string
  channel: string
  recipient: string | null
  subject: string
  status: string
  attempts: number
  max_attempts: number
  next_attempt_at: string
  last_error: string | null
  sent_at: string | null
}

const STATUS_COLOR: Record<string, string> = { PENDING: 'blue', SENDING: 'indigo', SENT: 'green', FAILED: 'red', SKIPPED: 'slate' }

export function NotificationLogsPage() {
  const { tr, lang } = useI18n()
  const toast = useToast()
  const [status, setStatus] = useState('')
  const [channel, setChannel] = useState('')
  const [page, setPage] = useState(1)
  const { data, error, loading, reload } = useApi<{ total: number; items: NotifLog[] }>(
    `/admin/notification-logs${queryString({ status, channel, page, page_size: 50 })}`,
  )
  async function retry(id: number) {
    try {
      await api.post(`/admin/notification-logs/${id}/retry`)
      toast.success(tr('ส่งเข้าคิวใหม่แล้ว', 'Queued for retry'))
      reload()
    } catch (e) {
      toast.error((e as ApiError).message)
    }
  }
  return (
    <div className="space-y-4">
      <PageHeader
        title={tr('บันทึกการส่งแจ้งเตือน', 'Notification log')}
        subtitle={tr('อีเมลและ LINE ส่งผ่านคิวเบื้องหลัง พร้อมการลองใหม่อัตโนมัติ', 'E-mail and LINE are delivered by the background worker with automatic retries')}
      />
      <div className="card flex flex-wrap gap-3 p-3">
        <select className="input w-auto py-2 text-sm" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} aria-label="status">
          <option value="">{tr('ทุกสถานะ', 'All statuses')}</option>
          {Object.keys(STATUS_COLOR).map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select className="input w-auto py-2 text-sm" value={channel} onChange={(e) => { setChannel(e.target.value); setPage(1) }} aria-label="channel">
          <option value="">EMAIL + LINE</option>
          <option value="EMAIL">EMAIL</option>
          <option value="LINE">LINE</option>
          <option value="IN_APP">IN_APP</option>
        </select>
        <button type="button" className="btn-secondary" onClick={reload}>
          {tr('รีเฟรช', 'Refresh')}
        </button>
      </div>
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      <div className="card overflow-x-auto">
        {!data && loading ? (
          <Loading />
        ) : !data?.items.length ? (
          <EmptyState title={tr('ไม่พบรายการ', 'No entries')} />
        ) : (
          <table className="table-base">
            <thead>
              <tr>
                <th>{tr('เวลา', 'Time')}</th>
                <th>Ticket</th>
                <th>{tr('เหตุการณ์', 'Event')}</th>
                <th>{tr('ช่องทาง / ผู้รับ', 'Channel / recipient')}</th>
                <th>{tr('สถานะ', 'Status')}</th>
                <th>{tr('ข้อผิดพลาดล่าสุด', 'Last error')}</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((n) => (
                <tr key={n.id}>
                  <td className="text-xs whitespace-nowrap">{formatDateTime(n.created_at, lang)}</td>
                  <td className="text-xs whitespace-nowrap">
                    {n.ticket_id ? (
                      <Link className="text-brand-700 hover:underline" to={`/admin/tickets/${n.ticket_id}`}>
                        {n.ticket_number}
                      </Link>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td className="text-xs">
                    <p className="font-mono">{n.event_type}</p>
                    <p className="max-w-xs truncate text-slate-500">{n.subject}</p>
                  </td>
                  <td className="text-xs">
                    {n.channel}
                    <p className="text-slate-500">{n.recipient}</p>
                  </td>
                  <td className="text-xs">
                    <Badge color={STATUS_COLOR[n.status] ?? 'gray'}>{n.status}</Badge>
                    <p className="mt-1 text-slate-500">
                      {n.attempts}/{n.max_attempts}
                    </p>
                  </td>
                  <td className="max-w-xs text-xs text-red-700">{n.last_error}</td>
                  <td>
                    {(n.status === 'FAILED' || n.status === 'SKIPPED') && n.channel !== 'IN_APP' && (
                      <button type="button" className="btn-secondary px-2.5 py-1 text-xs" onClick={() => retry(n.id)}>
                        {tr('ส่งใหม่', 'Retry')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data && data.total > 0 && <Pagination page={page} pageSize={50} total={data.total} onPage={setPage} />}
      </div>
    </div>
  )
}
