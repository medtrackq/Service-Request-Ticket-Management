import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { queryString } from '../api/client'
import type { DashboardData } from '../api/types'
import { COLOR_HEX, ErrorBox, Loading, cx } from '../components/ui'
import { useI18n } from '../i18n'
import { formatDateTime, formatMonth } from '../lib/dates'
import { PageHeader } from './AdminLayout'
import { FILTER_KEYS, TicketFilterBar, filtersToQuery, type FilterValues } from './Filters'
import { useApi } from './useApi'

const BRAND = '#145fae'
const GRID = '#e2e8f0'
const AXIS = { fontSize: 12, fill: '#64748b' }

function useFilterParams(): [FilterValues, (v: FilterValues) => void] {
  const [params, setParams] = useSearchParams()
  const value: FilterValues = {}
  for (const k of FILTER_KEYS) {
    const v = params.get(k)
    if (v) value[k] = v
  }
  return [value, (v) => setParams(filtersToQuery(v), { replace: true })]
}

export function DashboardPage() {
  const { tr, pick, lang } = useI18n()
  const [filters, setFilters] = useFilterParams()
  const qs = queryString(filtersToQuery(filters))
  const { data, error, loading, reload } = useApi<DashboardData>(`/dashboard${qs}`)

  const ticketsLink = (extra: Record<string, string>) =>
    `/admin/tickets${queryString({ ...filtersToQuery({ ...filters, status: undefined, status_category: undefined }), ...extra })}`

  const cards = data
    ? [
        { key: 'total', th: 'Ticket ทั้งหมด', en: 'Total tickets', value: data.kpis.total, to: ticketsLink({}), tone: 'navy' },
        { key: 'new', th: 'รับเรื่องใหม่', en: 'New', value: data.kpis.new, to: ticketsLink({ status: 'NEW' }), tone: 'blue' },
        { key: 'open', th: 'งานที่ยังเปิดอยู่', en: 'Open', value: data.kpis.open, to: ticketsLink({ status_category: 'ACTIVE' }), tone: 'indigo' },
        { key: 'in_progress', th: 'กำลังดำเนินการ', en: 'In progress', value: data.kpis.in_progress, to: ticketsLink({ status: 'IN_PROGRESS' }), tone: 'amber' },
        { key: 'waiting', th: 'รอข้อมูล', en: 'Waiting', value: data.kpis.waiting, to: ticketsLink({ status_category: 'WAITING' }), tone: 'orange' },
        { key: 'resolved', th: 'ดำเนินการเสร็จสิ้น', en: 'Resolved', value: data.kpis.resolved, to: ticketsLink({ status: 'RESOLVED' }), tone: 'green' },
        { key: 'closed', th: 'ปิดงาน', en: 'Closed', value: data.kpis.closed, to: ticketsLink({ status: 'CLOSED' }), tone: 'slate' },
        { key: 'overdue', th: 'เกินกำหนด', en: 'Overdue', value: data.kpis.overdue, to: ticketsLink({ overdue: 'true' }), tone: 'red' },
      ]
    : []

  const volume = useMemo(() => (data?.volume_by_month ?? []).map((r) => ({ ...r, label: formatMonth(r.month, lang) })), [data, lang])

  return (
    <div className="space-y-5">
      <PageHeader
        title={tr('แดชบอร์ด', 'Dashboard')}
        subtitle={
          data
            ? tr(`ข้อมูลจากฐานข้อมูล ณ ${formatDateTime(data.generated_at, lang)}`, `Live data as of ${formatDateTime(data.generated_at, lang)}`)
            : undefined
        }
        actions={
          <button type="button" className="btn-secondary" onClick={reload}>
            {tr('รีเฟรช', 'Refresh')}
          </button>
        }
      />
      <TicketFilterBar value={filters} onChange={setFilters} />

      {data && data.kpis.sample > 0 && (
        <div className="rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-2.5 text-sm text-yellow-900" role="status" data-testid="sample-banner">
          ⚠️{' '}
          {tr(
            `มีข้อมูลตัวอย่าง (Sample) ${data.kpis.sample} รายการรวมอยู่ในสถิตินี้ — ปิด "รวมข้อมูลตัวอย่าง" เพื่อดูเฉพาะข้อมูลจริง`,
            `${data.kpis.sample} sample (demo) tickets are included — turn off "Include sample data" to see real data only.`,
          )}
        </div>
      )}

      {error && <ErrorBox message={error.message} onRetry={reload} />}
      {!data && loading && <Loading />}

      {data && (
        <>
          <div className={cx('grid grid-cols-2 gap-3 md:grid-cols-4', loading && 'opacity-60')}>
            {cards.map((c) => (
              <Link
                key={c.key}
                to={c.to}
                className={cx(
                  'card group p-4 transition hover:-translate-y-0.5 hover:shadow-md',
                  c.key === 'overdue' && c.value > 0 && 'border-red-200 bg-red-50/60',
                )}
              >
                <p className="text-xs font-medium text-slate-500">{lang === 'en' ? c.en : c.th}</p>
                <p className={cx('mt-1 text-3xl font-bold tabular-nums', c.key === 'overdue' && c.value > 0 ? 'text-red-700' : 'text-navy-900')}>
                  {c.value.toLocaleString()}
                </p>
                <p className="mt-1 text-xs text-brand-700 opacity-0 transition group-hover:opacity-100">{tr('ดูรายการ →', 'View list →')}</p>
              </Link>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title={tr('ปริมาณ Ticket รายเดือน', 'Ticket volume by month')}>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={volume} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
                  <defs>
                    <linearGradient id="vol" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={BRAND} stopOpacity={0.25} />
                      <stop offset="100%" stopColor={BRAND} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={GRID} vertical={false} />
                  <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
                  <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
                  <Tooltip formatter={(v) => [v as number, tr('Ticket', 'Tickets')]} />
                  <Area type="monotone" dataKey="count" stroke={BRAND} strokeWidth={2} fill="url(#vol)" />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title={tr('Ticket ตามสถานะ', 'Tickets by status')}>
              <HBar
                data={data.by_status.map((s) => ({ name: pick(s, 'name'), count: s.count, color: COLOR_HEX[s.color] ?? BRAND }))}
                colored
              />
            </ChartCard>

            <ChartCard title={tr('Ticket ตามประเภทคำขอ', 'Tickets by request type')}>
              <HBar data={data.by_request_type.map((r) => ({ name: pick(r, 'name'), count: r.count }))} />
            </ChartCard>

            <ChartCard title={tr('Ticket ตามแผนก', 'Tickets by department')}>
              <HBar data={data.by_department.map((r) => ({ name: pick(r, 'name'), count: r.count }))} />
            </ChartCard>

            <ChartCard
              title={tr('เวลาดำเนินการเฉลี่ย (ชั่วโมง) ตามประเภทคำขอ', 'Average resolution time (hours) by request type')}
              note={tr('คำนวณจาก Ticket ที่เสร็จสิ้น/ปิดแล้ว: เวลาแก้ไขเสร็จ − เวลาสร้าง', 'Resolved/closed tickets: resolved time − created time')}
            >
              {data.resolution_by_request_type.length === 0 ? (
                <p className="py-16 text-center text-sm text-slate-500">{tr('ยังไม่มี Ticket ที่ดำเนินการเสร็จ', 'No resolved tickets yet')}</p>
              ) : (
                <HBar data={data.resolution_by_request_type.map((r) => ({ name: pick(r, 'name'), count: r.avg_hours ?? 0 }))} unit={tr(' ชม.', ' h')} />
              )}
            </ChartCard>

            <ChartCard title={tr('Ticket ตามระดับความสำคัญ', 'Tickets by priority')}>
              <HBar
                data={data.by_priority.map((p) => ({
                  name: p.priority,
                  count: p.count,
                  color: { LOW: '#94a3b8', NORMAL: '#2477cc', HIGH: '#ea580c', URGENT: '#dc2626' }[p.priority],
                }))}
                colored
              />
            </ChartCard>
          </div>
        </>
      )}
    </div>
  )
}

function ChartCard({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="card p-4">
      <h2 className="text-sm font-semibold text-navy-900">{title}</h2>
      {note && <p className="text-xs text-slate-500">{note}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

function HBar({ data, colored, unit }: { data: { name: string; count: number; color?: string }[]; colored?: boolean; unit?: string }) {
  const height = Math.max(160, data.length * 38 + 30)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, left: 8, bottom: 0 }}>
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis type="number" allowDecimals={!!unit} tick={AXIS} tickLine={false} axisLine={false} />
        <YAxis type="category" dataKey="name" width={150} tick={{ ...AXIS, fill: '#334155' }} tickLine={false} axisLine={false} />
        <Tooltip formatter={(v) => [`${v}${unit ?? ''}`, '']} cursor={{ fill: '#f1f5f9' }} />
        <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={20} label={{ position: 'right', fontSize: 12, fill: '#334155' }}>
          {data.map((d, i) => (
            <Cell key={i} fill={colored && d.color ? d.color : BRAND} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
