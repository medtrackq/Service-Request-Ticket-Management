import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { API_BASE, queryString } from '../api/client'
import type { PerfBlock, PerformanceReport, SummaryReport, WorkloadRow } from '../api/types'
import { IconDownload } from '../components/Icons'
import { ErrorBox, Loading, PriorityBadge, SectionCard, cx } from '../components/ui'
import { ROLE_LABELS, label, useI18n } from '../i18n'
import { formatDateTime, formatMonth, hoursLabel } from '../lib/dates'
import { PageHeader } from './AdminLayout'
import { TicketFilterBar, filtersToQuery, type FilterValues } from './Filters'
import { useApi } from './useApi'

type Tab = 'summary' | 'workload' | 'performance'

export function ReportsPage() {
  const { tr } = useI18n()
  const [tab, setTab] = useState<Tab>('summary')
  const [filters, setFilters] = useState<FilterValues>({})
  const qs = filtersToQuery(filters)
  const csvHref = `${API_BASE}/reports/${tab}${queryString({ ...qs, format: 'csv' })}`
  const tabs: { id: Tab; th: string; en: string }[] = [
    { id: 'summary', th: 'สรุป Ticket', en: 'Ticket summary' },
    { id: 'workload', th: 'ภาระงานเจ้าหน้าที่', en: 'Staff workload' },
    { id: 'performance', th: 'ประสิทธิภาพการให้บริการ', en: 'Ticket performance' },
  ]
  return (
    <div className="space-y-4">
      <PageHeader
        title={tr('รายงาน', 'Reports')}
        subtitle={tr('คำนวณจากข้อมูลจริงในฐานข้อมูล ตามตัวกรองที่เลือก (วันที่ = วันที่สร้าง Ticket)', 'Calculated from database records using the selected filters (date = ticket creation date)')}
        actions={
          <a className="btn-secondary" href={csvHref} download>
            <IconDownload size={16} /> CSV
          </a>
        }
      />
      <div className="flex gap-1 overflow-x-auto rounded-xl bg-white p-1 shadow-sm ring-1 ring-slate-200" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cx('rounded-lg px-4 py-2 text-sm font-medium whitespace-nowrap', tab === t.id ? 'bg-navy-900 text-white' : 'text-slate-600 hover:bg-slate-100')}
          >
            {tr(t.th, t.en)}
          </button>
        ))}
      </div>
      <TicketFilterBar value={filters} onChange={setFilters} show={['date', 'department', 'request_type', 'priority', 'sample']} />
      {tab === 'summary' && <Summary qs={queryString(qs)} />}
      {tab === 'workload' && <Workload qs={queryString(qs)} />}
      {tab === 'performance' && <Performance qs={queryString(qs)} />}
    </div>
  )
}

function SimpleTable({ head, rows }: { head: ReactNode[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="table-base">
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i} className={i > 0 ? 'text-right' : undefined}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => (
                <td key={j} className={j > 0 ? 'text-right tabular-nums' : undefined}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Summary({ qs }: { qs: string }) {
  const { tr, pick, lang } = useI18n()
  const { data, error, reload } = useApi<SummaryReport>(`/reports/summary${qs}`)
  if (error) return <ErrorBox message={error.message} onRetry={reload} />
  if (!data) return <Loading />
  const n = tr('จำนวน', 'Tickets')
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <SectionCard title={tr(`ตามประเภทคำขอ (รวม ${data.total})`, `By request type (total ${data.total})`)}>
        <SimpleTable head={[tr('ประเภท', 'Type'), n]} rows={data.by_request_type.map((r) => [pick(r, 'name'), r.count])} />
      </SectionCard>
      <SectionCard title={tr('ตามแผนก', 'By department')}>
        <SimpleTable head={[tr('แผนก', 'Department'), n]} rows={data.by_department.map((r) => [pick(r, 'name'), r.count])} />
      </SectionCard>
      <SectionCard title={tr('ตามสถานะ', 'By status')}>
        <SimpleTable head={[tr('สถานะ', 'Status'), n]} rows={data.by_status.map((r) => [pick(r, 'name'), r.count])} />
      </SectionCard>
      <SectionCard title={tr('ตามเดือน (เวลาไทย)', 'By month (Bangkok time)')}>
        <SimpleTable head={[tr('เดือน', 'Month'), n]} rows={data.by_month.map((r) => [formatMonth(r.month, lang), r.count])} />
      </SectionCard>
    </div>
  )
}

function Workload({ qs }: { qs: string }) {
  const { tr, lang } = useI18n()
  const { data, error, reload } = useApi<{ rows: WorkloadRow[] }>(`/reports/workload${qs}`)
  if (error) return <ErrorBox message={error.message} onRetry={reload} />
  if (!data) return <Loading />
  return (
    <SectionCard title={tr('ภาระงานเจ้าหน้าที่ (ตามผู้รับผิดชอบปัจจุบัน)', 'Staff workload (by current assignee)')}>
      <SimpleTable
        head={[
          tr('เจ้าหน้าที่', 'Staff'),
          tr('ได้รับมอบหมาย', 'Assigned'),
          tr('งานที่ยังเปิด', 'Active'),
          tr('รอข้อมูล', 'Waiting'),
          tr('เสร็จสิ้น', 'Resolved'),
          tr('ปิดงาน', 'Closed'),
          tr('เกินกำหนด', 'Overdue'),
        ]}
        rows={data.rows.map((r) => [
          <div key="n">
            <p className="font-medium text-slate-800">{r.full_name}</p>
            <p className="text-xs text-slate-500">
              {label(ROLE_LABELS, r.role, lang)} {r.departments.length > 0 && `· ${r.departments.join(', ')}`}
            </p>
          </div>,
          r.assigned,
          r.active,
          r.waiting,
          r.resolved,
          r.closed,
          <span key="o" className={cx(r.overdue > 0 && 'font-semibold text-red-700')}>
            {r.overdue}
          </span>,
        ])}
      />
      <Definitions
        items={[
          [tr('ได้รับมอบหมาย', 'Assigned'), tr('Ticket ตามตัวกรองที่ผู้ใช้นี้เป็นผู้รับผิดชอบปัจจุบัน', 'Filtered tickets whose current assignee is this user')],
          [tr('งานที่ยังเปิด', 'Active'), tr('สถานะกลุ่ม ใหม่/กำลังดำเนินการ/รอข้อมูล', 'Status category NEW, OPEN or WAITING')],
          [tr('เกินกำหนด', 'Overdue'), tr('งานที่ยังเปิดและเลยกำหนดเสร็จแล้ว', 'Open tickets past their due date')],
        ]}
      />
    </SectionCard>
  )
}

function Performance({ qs }: { qs: string }) {
  const { tr, lang } = useI18n()
  const { data, error, reload } = useApi<PerformanceReport>(`/reports/performance${qs}`)
  if (error) return <ErrorBox message={error.message} onRetry={reload} />
  if (!data) return <Loading />
  const o = data.overall
  const pct = (v: number | null) => (v == null ? '-' : `${v}%`)
  const perfRows = (rows: PerfBlock[], key: 'request_type' | 'priority') =>
    rows.map((r) => [
      key === 'priority' ? <PriorityBadge key="p" priority={r.priority ?? ''} /> : r.request_type,
      r.tickets,
      hoursLabel(r.first_response_avg_hours, lang),
      hoursLabel(r.first_response_median_hours, lang),
      pct(r.first_response_target_met_pct),
      r.resolved,
      hoursLabel(r.resolution_avg_hours, lang),
      hoursLabel(r.resolution_median_hours, lang),
      pct(r.resolution_target_met_pct),
    ])
  const head = [
    '',
    tr('Ticket', 'Tickets'),
    tr('ตอบกลับครั้งแรก (เฉลี่ย)', 'First response avg'),
    tr('(มัธยฐาน)', '(median)'),
    tr('ตามเป้า', 'Within target'),
    tr('เสร็จสิ้น', 'Resolved'),
    tr('เวลาแก้ไข (เฉลี่ย)', 'Resolution avg'),
    tr('(มัธยฐาน)', '(median)'),
    tr('ตามเป้า', 'Within target'),
  ]
  const maxAging = Math.max(1, ...data.open_aging.map((a) => a.count))
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={tr('ตอบกลับครั้งแรก (เฉลี่ย)', 'Avg first response')} value={hoursLabel(o.first_response_avg_hours, lang)} sub={tr(`ตามเป้า ${pct(o.first_response_target_met_pct)}`, `within target ${pct(o.first_response_target_met_pct)}`)} />
        <Stat label={tr('เวลาแก้ไขเสร็จ (เฉลี่ย)', 'Avg resolution time')} value={hoursLabel(o.resolution_avg_hours, lang)} sub={tr(`ตามเป้า ${pct(o.resolution_target_met_pct)}`, `within target ${pct(o.resolution_target_met_pct)}`)} />
        <Stat label={tr('Ticket ที่เสร็จสิ้น/ปิด', 'Resolved / closed')} value={String(o.resolved)} sub={tr(`จาก ${o.tickets} รายการ`, `of ${o.tickets}`)} />
        <Stat label={tr('งานเกินกำหนด', 'Overdue tickets')} value={String(data.overdue.length)} danger={data.overdue.length > 0} />
      </div>
      <SectionCard title={tr('ตามประเภทคำขอ', 'By request type')}>
        <SimpleTable head={head} rows={perfRows(data.by_request_type, 'request_type')} />
      </SectionCard>
      <SectionCard title={tr('ตามระดับความสำคัญ', 'By priority')}>
        <SimpleTable head={head} rows={perfRows(data.by_priority, 'priority')} />
      </SectionCard>
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title={tr('อายุของงานที่ยังเปิดอยู่', 'Open ticket aging')}>
          <ul className="space-y-2">
            {data.open_aging.map((a) => (
              <li key={a.bucket} className="grid grid-cols-[70px_minmax(0,1fr)_40px] items-center gap-2 text-sm">
                <span className="text-slate-600">{a.bucket}</span>
                <span className="h-3 rounded-full bg-slate-100">
                  <span className="block h-3 rounded-full bg-brand-500" style={{ width: `${(a.count / maxAging) * 100}%` }} />
                </span>
                <span className="text-right tabular-nums">{a.count}</span>
              </li>
            ))}
          </ul>
        </SectionCard>
        <SectionCard title={tr('เป้าหมายการให้บริการภายใน (ชั่วโมง)', 'Internal service targets (hours)')}>
          <SimpleTable
            head={[tr('ความสำคัญ', 'Priority'), tr('ตอบกลับครั้งแรก', 'First response'), tr('แก้ไขเสร็จ', 'Resolution')]}
            rows={['URGENT', 'HIGH', 'NORMAL', 'LOW'].map((p) => [
              <PriorityBadge key={p} priority={p} />,
              data.targets[p]?.first_response_hours ?? '-',
              data.targets[p]?.resolution_hours ?? '-',
            ])}
          />
          <p className="mt-2 text-xs text-slate-500">
            {tr('เป็นเป้าหมายภายในที่ตั้งค่าได้ (ไม่ใช่ SLA ตามสัญญา) — แก้ไขได้ที่ ตั้งค่าระบบ › service_targets', 'Configurable internal targets (not contractual SLAs) — edit in Settings › service_targets')}
          </p>
        </SectionCard>
      </div>
      <SectionCard title={tr(`งานเกินกำหนด (${data.overdue.length})`, `Overdue tickets (${data.overdue.length})`)}>
        {data.overdue.length === 0 ? (
          <p className="text-sm text-slate-500">{tr('ไม่มีงานเกินกำหนด', 'No overdue tickets')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-base">
              <thead>
                <tr>
                  <th>{tr('เลขที่', 'Ticket')}</th>
                  <th>{tr('เรื่อง', 'Subject')}</th>
                  <th>{tr('ความสำคัญ', 'Priority')}</th>
                  <th>{tr('แผนก', 'Department')}</th>
                  <th>{tr('ผู้รับผิดชอบ', 'Assignee')}</th>
                  <th>{tr('กำหนดเสร็จ', 'Due')}</th>
                  <th className="text-right">{tr('เกินมา', 'Overdue by')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.overdue.map((r) => (
                  <tr key={r.id}>
                    <td className="whitespace-nowrap">
                      <Link className="font-medium text-brand-700 hover:underline" to={`/admin/tickets/${r.id}`}>
                        {r.ticket_number}
                      </Link>
                    </td>
                    <td className="max-w-xs truncate">{r.subject}</td>
                    <td>
                      <PriorityBadge priority={r.priority} />
                    </td>
                    <td className="whitespace-nowrap">{r.department}</td>
                    <td className="whitespace-nowrap">{r.assigned_user ?? '-'}</td>
                    <td className="whitespace-nowrap">{formatDateTime(r.due_at, lang)}</td>
                    <td className="text-right font-medium text-red-700">{hoursLabel(r.hours_overdue, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
      <Definitions
        items={[
          [
            tr('ตอบกลับครั้งแรก', 'First response'),
            tr(
              'เวลาตั้งแต่สร้าง Ticket จนถึงการดำเนินการครั้งแรกของเจ้าหน้าที่ที่ลูกค้าเห็นได้ (เปลี่ยนสถานะด้วยตนเอง หรือข้อความถึงลูกค้า) ไม่นับการเปลี่ยนสถานะอัตโนมัติและบันทึกภายใน',
              'Time from creation to the first customer-visible staff action (manual status change or customer-visible update). Automatic transitions and internal notes do not count.',
            ),
          ],
          [
            tr('เวลาแก้ไขเสร็จ', 'Resolution time'),
            tr(
              'เวลาตั้งแต่สร้างจนถึงสถานะ "ดำเนินการเสร็จสิ้น" (หรือเวลาปิดงาน หากปิดโดยไม่ผ่าน Resolved) เฉพาะ Ticket ที่เสร็จสิ้น/ปิดแล้ว',
              'Time from creation to RESOLVED (or closing time when closed without RESOLVED), for resolved/closed tickets only.',
            ),
          ],
          [tr('อายุงานที่เปิดอยู่', 'Open ticket aging'), tr('เวลาปัจจุบัน − เวลาสร้าง สำหรับงานที่ยังไม่เสร็จ/ปิด/ยกเลิก', 'Now − created time for tickets not resolved/closed/cancelled.')],
          [tr('เกินกำหนด', 'Overdue'), tr('งานที่ยังเปิดอยู่และเลยวันครบกำหนด (due date) แล้ว', 'Open tickets whose due date has passed.')],
          [tr('ตามเป้า', 'Within target'), tr('ร้อยละของ Ticket ที่ใช้เวลาไม่เกินเป้าหมายตามระดับความสำคัญ', 'Share of tickets within the internal target for their priority.')],
        ]}
      />
    </div>
  )
}

function Stat({ label, value, sub, danger }: { label: string; value: string; sub?: string; danger?: boolean }) {
  return (
    <div className={cx('card p-4', danger && 'border-red-200 bg-red-50/60')}>
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={cx('mt-1 text-2xl font-bold', danger ? 'text-red-700' : 'text-navy-900')}>{value}</p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
  )
}

function Definitions({ items }: { items: [string, string][] }) {
  const { tr } = useI18n()
  return (
    <details className="card mt-4 p-4 text-sm">
      <summary className="cursor-pointer font-semibold text-navy-900">{tr('นิยามการคำนวณ', 'Calculation definitions')}</summary>
      <dl className="mt-3 space-y-2">
        {items.map(([k, v]) => (
          <div key={k}>
            <dt className="font-medium text-slate-800">{k}</dt>
            <dd className="text-slate-600">{v}</dd>
          </div>
        ))}
      </dl>
    </details>
  )
}
