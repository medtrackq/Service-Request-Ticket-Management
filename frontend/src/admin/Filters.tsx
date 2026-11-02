import type { ReactNode } from 'react'
import { Toggle } from '../components/ui'
import { PRIORITY_LABELS, useI18n } from '../i18n'
import { useLookups } from './auth'

export interface FilterValues {
  date_from?: string
  date_to?: string
  department_id?: string
  request_type?: string
  status?: string
  status_category?: string
  priority?: string
  assigned?: string
  include_sample?: string
  q?: string
  overdue?: string
}

export const FILTER_KEYS: (keyof FilterValues)[] = [
  'q',
  'date_from',
  'date_to',
  'department_id',
  'request_type',
  'status',
  'status_category',
  'priority',
  'assigned',
  'overdue',
  'include_sample',
]

export function filtersToQuery(f: FilterValues): Record<string, string> {
  const out: Record<string, string> = {}
  for (const k of FILTER_KEYS) {
    const v = f[k]
    if (v !== undefined && v !== '') out[k] = v
  }
  return out
}

function Sel({ label, value, onChange, children }: { label: string; value: string; onChange: (v: string) => void; children: ReactNode }) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
      <select className="input py-2 text-sm" value={value} onChange={(e) => onChange(e.target.value)}>
        {children}
      </select>
    </label>
  )
}

export function TicketFilterBar({
  value,
  onChange,
  show = ['date', 'department', 'request_type', 'status', 'priority', 'assigned', 'sample'],
  extra,
}: {
  value: FilterValues
  onChange: (v: FilterValues) => void
  show?: ('date' | 'department' | 'request_type' | 'status' | 'status_category' | 'priority' | 'assigned' | 'sample')[]
  extra?: ReactNode
}) {
  const { tr, pick } = useI18n()
  const { lookups } = useLookups()
  const set = (k: keyof FilterValues, v: string) => onChange({ ...value, [k]: v })
  const all = tr('ทั้งหมด', 'All')
  return (
    <div className="card grid grid-cols-2 gap-3 p-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
      {extra}
      {show.includes('date') && (
        <>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">{tr('ตั้งแต่วันที่', 'From')}</span>
            <input type="date" className="input py-2 text-sm" value={value.date_from ?? ''} onChange={(e) => set('date_from', e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">{tr('ถึงวันที่', 'To')}</span>
            <input type="date" className="input py-2 text-sm" value={value.date_to ?? ''} onChange={(e) => set('date_to', e.target.value)} />
          </label>
        </>
      )}
      {show.includes('department') && (
        <Sel label={tr('แผนก', 'Department')} value={value.department_id ?? ''} onChange={(v) => set('department_id', v)}>
          <option value="">{all}</option>
          {lookups?.departments.map((d) => (
            <option key={d.id} value={d.id}>
              {pick(d, 'name')}
            </option>
          ))}
        </Sel>
      )}
      {show.includes('request_type') && (
        <Sel label={tr('ประเภทคำขอ', 'Request type')} value={value.request_type ?? ''} onChange={(v) => set('request_type', v)}>
          <option value="">{all}</option>
          {lookups?.request_types.map((r) => (
            <option key={r.code} value={r.code}>
              {pick(r, 'name')}
            </option>
          ))}
        </Sel>
      )}
      {show.includes('status_category') && (
        <Sel label={tr('กลุ่มสถานะ', 'Status group')} value={value.status_category ?? ''} onChange={(v) => set('status_category', v)}>
          <option value="">{all}</option>
          <option value="ACTIVE">{tr('งานที่ยังเปิดอยู่', 'Open (active)')}</option>
          <option value="NEW">{tr('ใหม่', 'New')}</option>
          <option value="OPEN">{tr('กำลังดำเนินการ', 'In process')}</option>
          <option value="WAITING">{tr('รอข้อมูล', 'Waiting')}</option>
          <option value="RESOLVED">{tr('เสร็จสิ้น', 'Resolved')}</option>
          <option value="CLOSED">{tr('ปิดงาน', 'Closed')}</option>
          <option value="CANCELLED">{tr('ยกเลิก', 'Cancelled')}</option>
        </Sel>
      )}
      {show.includes('status') && (
        <Sel label={tr('สถานะ', 'Status')} value={value.status ?? ''} onChange={(v) => set('status', v)}>
          <option value="">{all}</option>
          {lookups?.statuses.map((s) => (
            <option key={s.code} value={s.code}>
              {pick(s, 'name')}
            </option>
          ))}
        </Sel>
      )}
      {show.includes('priority') && (
        <Sel label={tr('ความสำคัญ', 'Priority')} value={value.priority ?? ''} onChange={(v) => set('priority', v)}>
          <option value="">{all}</option>
          {(lookups?.priorities ?? ['LOW', 'NORMAL', 'HIGH', 'URGENT']).map((p) => (
            <option key={p} value={p}>
              {pick({ label_th: PRIORITY_LABELS[p].th, label_en: PRIORITY_LABELS[p].en }, 'label')}
            </option>
          ))}
        </Sel>
      )}
      {show.includes('assigned') && (
        <Sel label={tr('ผู้รับผิดชอบ', 'Assigned staff')} value={value.assigned ?? ''} onChange={(v) => set('assigned', v)}>
          <option value="">{all}</option>
          <option value="me">{tr('งานของฉัน', 'Assigned to me')}</option>
          <option value="none">{tr('ยังไม่มอบหมาย', 'Unassigned')}</option>
          {lookups?.users.map((u) => (
            <option key={u.id} value={String(u.id)}>
              {u.full_name}
            </option>
          ))}
        </Sel>
      )}
      {show.includes('sample') && (
        <div className="flex items-end pb-1.5">
          <Toggle
            checked={value.include_sample !== 'false'}
            onChange={(v) => set('include_sample', v ? '' : 'false')}
            label={tr('รวมข้อมูลตัวอย่าง', 'Include sample data')}
          />
        </div>
      )}
    </div>
  )
}
