import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { API_BASE, ApiError, api, queryString } from '../api/client'
import type { Page, TicketListItem } from '../api/types'
import { IconDownload, IconSearch } from '../components/Icons'
import { useToast } from '../components/Toast'
import { EmptyState, ErrorBox, Loading, Modal, Pagination, PriorityBadge, SampleBadge, Spinner, StatusBadge, cx } from '../components/ui'
import { PRIORITY_LABELS, useI18n } from '../i18n'
import { formatDateTime, fromBangkokLocalInput } from '../lib/dates'
import { PageHeader } from './AdminLayout'
import { useAuth, useLookups } from './auth'
import { FILTER_KEYS, TicketFilterBar, filtersToQuery, type FilterValues } from './Filters'
import { useApi } from './useApi'

const PAGE_SIZE = 25

export function TicketsPage() {
  const { tr, pick, lang } = useI18n()
  const { permissions } = useAuth()
  const [params, setParams] = useSearchParams()
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [bulkOpen, setBulkOpen] = useState(false)
  const [search, setSearch] = useState(params.get('q') ?? '')

  const filters: FilterValues = {}
  for (const k of FILTER_KEYS) {
    const v = params.get(k)
    if (v) filters[k] = v
  }
  const sort = params.get('sort') ?? 'created_at'
  const direction = params.get('direction') ?? 'desc'
  const page = Number(params.get('page') ?? '1') || 1

  const query = { ...filtersToQuery(filters), sort, direction, page, page_size: PAGE_SIZE }
  const { data, error, loading, reload } = useApi<Page<TicketListItem>>(`/tickets${queryString(query)}`)

  useEffect(() => setSelected(new Set()), [data])

  const update = (next: Record<string, string | undefined>, resetPage = true) => {
    const merged: Record<string, string> = {}
    params.forEach((v, k) => (merged[k] = v))
    for (const [k, v] of Object.entries(next)) {
      if (v === undefined || v === '') delete merged[k]
      else merged[k] = v
    }
    if (resetPage) delete merged.page
    setParams(merged, { replace: true })
  }

  const setFilters = (f: FilterValues) => {
    const next: Record<string, string | undefined> = {}
    for (const k of FILTER_KEYS) next[k] = f[k]
    next.q = params.get('q') ?? undefined
    update(next)
  }

  const toggleSort = (col: string) => {
    if (sort === col) update({ direction: direction === 'asc' ? 'desc' : 'asc' }, false)
    else update({ sort: col, direction: col === 'ticket_number' ? 'asc' : 'desc' }, false)
  }

  const exportHref = `${API_BASE}/tickets/export.csv${queryString(filtersToQuery(filters))}`
  const items = data?.items ?? []
  const allChecked = items.length > 0 && items.every((t) => selected.has(t.id))

  const Th = ({ col, children }: { col?: string; children: React.ReactNode }) => (
    <th scope="col" aria-sort={col && sort === col ? (direction === 'asc' ? 'ascending' : 'descending') : undefined}>
      {col ? (
        <button type="button" onClick={() => toggleSort(col)} className="inline-flex items-center gap-1 hover:text-navy-900">
          {children}
          <span className="text-[10px] text-slate-400">{sort === col ? (direction === 'asc' ? '▲' : '▼') : '↕'}</span>
        </button>
      ) : (
        children
      )}
    </th>
  )

  return (
    <div className="space-y-4">
      <PageHeader
        title={tr('รายการ Ticket', 'Tickets')}
        subtitle={data ? tr(`ทั้งหมด ${data.total} รายการ`, `${data.total} tickets`) : undefined}
        actions={
          <>
            {permissions?.can_bulk_assign && (
              <button type="button" className="btn-secondary" disabled={selected.size === 0} onClick={() => setBulkOpen(true)}>
                {tr(`มอบหมายงานที่เลือก (${selected.size})`, `Bulk assign (${selected.size})`)}
              </button>
            )}
            {permissions?.can_export && (
              <a className="btn-secondary" href={exportHref} download>
                <IconDownload size={16} /> CSV
              </a>
            )}
          </>
        }
      />

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          update({ q: search.trim() || undefined })
        }}
      >
        <div className="relative flex-1">
          <IconSearch size={18} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-slate-400" />
          <input
            className="input pl-10"
            placeholder={tr('ค้นหา เลขที่ Ticket, ลูกค้า, ผู้ติดต่อ, เบอร์โทร, Serial Number...', 'Search ticket no., customer, contact, phone, serial number...')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label={tr('ค้นหา', 'Search')}
          />
        </div>
        <button type="submit" className="btn-primary">
          {tr('ค้นหา', 'Search')}
        </button>
      </form>

      <TicketFilterBar
        value={filters}
        onChange={setFilters}
        show={['date', 'department', 'request_type', 'status_category', 'status', 'priority', 'assigned', 'sample']}
      />
      {filters.overdue === 'true' && (
        <p className="text-sm">
          <span className="rounded-full bg-red-100 px-3 py-1 font-medium text-red-700">{tr('แสดงเฉพาะงานเกินกำหนด', 'Overdue only')}</span>{' '}
          <button type="button" className="text-brand-700 underline" onClick={() => update({ overdue: undefined })}>
            {tr('ล้าง', 'clear')}
          </button>
        </p>
      )}

      {error && <ErrorBox message={error.message} onRetry={reload} />}
      <div className="card overflow-hidden">
        {!data && loading ? (
          <Loading />
        ) : items.length === 0 ? (
          <EmptyState title={tr('ไม่พบ Ticket ตามเงื่อนไข', 'No tickets match the filters')} />
        ) : (
          <div className={cx('overflow-x-auto', loading && 'opacity-60')}>
            <table className="table-base">
              <thead>
                <tr>
                  {permissions?.can_bulk_assign && (
                    <th className="w-8">
                      <input
                        type="checkbox"
                        aria-label={tr('เลือกทั้งหมด', 'Select all')}
                        checked={allChecked}
                        onChange={() => setSelected(allChecked ? new Set() : new Set(items.map((t) => t.id)))}
                      />
                    </th>
                  )}
                  <Th col="ticket_number">{tr('เลขที่ Ticket', 'Ticket number')}</Th>
                  <Th col="created_at">{tr('วันที่สร้าง', 'Created')}</Th>
                  <Th>{tr('ลูกค้า', 'Customer')}</Th>
                  <Th>{tr('ประเภทคำขอ', 'Request type')}</Th>
                  <Th>{tr('เรื่อง', 'Subject')}</Th>
                  <Th col="priority">{tr('ความสำคัญ', 'Priority')}</Th>
                  <Th col="status">{tr('สถานะ', 'Status')}</Th>
                  <Th>{tr('แผนก', 'Department')}</Th>
                  <Th>{tr('ผู้รับผิดชอบ', 'Assigned')}</Th>
                  <Th col="last_activity_at">{tr('อัปเดตล่าสุด', 'Last updated')}</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((t) => (
                  <tr key={t.id} className={cx('hover:bg-slate-50', t.is_overdue && 'bg-red-50/50')}>
                    {permissions?.can_bulk_assign && (
                      <td>
                        <input
                          type="checkbox"
                          aria-label={t.ticket_number}
                          checked={selected.has(t.id)}
                          onChange={() =>
                            setSelected((s) => {
                              const n = new Set(s)
                              if (n.has(t.id)) n.delete(t.id)
                              else n.add(t.id)
                              return n
                            })
                          }
                        />
                      </td>
                    )}
                    <td className="whitespace-nowrap">
                      <Link to={`/admin/tickets/${t.id}`} className="font-semibold text-brand-700 hover:underline">
                        {t.ticket_number}
                      </Link>
                      <div className="mt-1 flex gap-1">
                        {t.is_sample && <SampleBadge />}
                        {t.is_overdue && (
                          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-medium text-red-700">{tr('เกินกำหนด', 'Overdue')}</span>
                        )}
                      </div>
                    </td>
                    <td className="whitespace-nowrap">{formatDateTime(t.created_at, lang)}</td>
                    <td className="max-w-[200px]">
                      <p className="truncate font-medium text-slate-800" title={t.customer_name}>
                        {t.customer_name}
                      </p>
                      <p className="truncate text-xs text-slate-500">{t.contact_name}</p>
                    </td>
                    <td className="whitespace-nowrap">{lang === 'en' ? t.request_type_name_en : t.request_type_name_th}</td>
                    <td className="max-w-[280px]">
                      <Link to={`/admin/tickets/${t.id}`} className="line-clamp-2 hover:text-brand-700" title={t.subject}>
                        {t.subject}
                      </Link>
                    </td>
                    <td>
                      <PriorityBadge priority={t.priority} />
                    </td>
                    <td>
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="whitespace-nowrap">{pick(t.department, 'name')}</td>
                    <td className="whitespace-nowrap">{t.assigned_user?.full_name ?? <span className="text-slate-400">—</span>}</td>
                    <td className="whitespace-nowrap">{formatDateTime(t.last_activity_at, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total > 0 && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={(p) => update({ page: String(p) }, false)} />}
      </div>

      <BulkAssignDialog
        open={bulkOpen}
        ticketIds={[...selected]}
        onClose={() => setBulkOpen(false)}
        onDone={() => {
          setBulkOpen(false)
          reload()
        }}
      />
    </div>
  )
}

function BulkAssignDialog({ open, ticketIds, onClose, onDone }: { open: boolean; ticketIds: number[]; onClose: () => void; onDone: () => void }) {
  const { tr, pick, lang } = useI18n()
  const { lookups } = useLookups()
  const toast = useToast()
  const [dept, setDept] = useState('')
  const [userId, setUserId] = useState('')
  const [priority, setPriority] = useState('')
  const [due, setDue] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ updated: string[]; failed: { ticket_id: number; message: string }[] } | null>(null)

  useEffect(() => {
    if (open) setResult(null)
  }, [open])

  const users = (lookups?.users ?? []).filter((u) => !dept || u.role === 'ADMIN' || u.department_ids.includes(Number(dept)))

  async function submit() {
    setBusy(true)
    try {
      const r = await api.post<{ updated: string[]; failed: { ticket_id: number; message: string }[] }>('/tickets/bulk-assign', {
        ticket_ids: ticketIds,
        department_id: dept ? Number(dept) : null,
        assigned_user_id: userId ? Number(userId) : null,
        priority: priority || null,
        due_at: fromBangkokLocalInput(due),
        reason: reason || null,
      })
      setResult(r)
      if (r.failed.length === 0) {
        toast.success(tr(`มอบหมายงานแล้ว ${r.updated.length} รายการ`, `${r.updated.length} tickets updated`))
        onDone()
      }
    } catch (e) {
      toast.error((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      title={tr(`มอบหมายงาน ${ticketIds.length} รายการ`, `Assign ${ticketIds.length} tickets`)}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={result ? onDone : onClose}>
            {result ? tr('ปิด', 'Close') : tr('ยกเลิก', 'Cancel')}
          </button>
          {!result && (
            <button type="button" className="btn-primary" onClick={submit} disabled={busy || (!dept && !userId && !priority && !due)}>
              {busy && <Spinner className="h-4 w-4" />} {tr('บันทึก', 'Apply')}
            </button>
          )}
        </>
      }
    >
      {result ? (
        <div className="space-y-2 text-sm">
          <p className="text-emerald-700">{tr(`สำเร็จ ${result.updated.length} รายการ`, `${result.updated.length} updated`)}</p>
          {result.failed.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-red-700">
              {result.failed.map((f) => (
                <li key={f.ticket_id}>
                  #{f.ticket_id}: {f.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <label className="block">
            <span className="label">{tr('แผนก (เว้นว่าง = ไม่เปลี่ยน)', 'Department (blank = unchanged)')}</span>
            <select className="input" value={dept} onChange={(e) => setDept(e.target.value)}>
              <option value="">—</option>
              {lookups?.departments.filter((d) => d.is_active).map((d) => (
                <option key={d.id} value={d.id}>
                  {pick(d, 'name')}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">{tr('ผู้รับผิดชอบ', 'Assignee')}</span>
            <select className="input" value={userId} onChange={(e) => setUserId(e.target.value)}>
              <option value="">—</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name}
                </option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="label">{tr('ความสำคัญ', 'Priority')}</span>
              <select className="input" value={priority} onChange={(e) => setPriority(e.target.value)}>
                <option value="">—</option>
                {Object.keys(PRIORITY_LABELS).map((p) => (
                  <option key={p} value={p}>
                    {PRIORITY_LABELS[p][lang]}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">{tr('กำหนดเสร็จ', 'Due date')}</span>
              <input type="datetime-local" className="input" value={due} onChange={(e) => setDue(e.target.value)} />
            </label>
          </div>
          <label className="block">
            <span className="label">{tr('เหตุผล', 'Reason')}</span>
            <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={2000} />
          </label>
        </div>
      )}
    </Modal>
  )
}
