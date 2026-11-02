import { useState } from 'react'
import { ApiError, api } from '../../api/client'
import { useToast } from '../../components/Toast'
import { Badge, ConfirmDialog, EmptyState, ErrorBox, Loading, Modal, Spinner, Toggle } from '../../components/ui'
import { CUSTOMER_TYPE_LABELS, PRIORITY_LABELS, label, useI18n } from '../../i18n'
import { PageHeader } from '../AdminLayout'
import { useLookups } from '../auth'
import { useApi } from '../useApi'

interface Rule {
  id: number
  name: string
  sort_order: number
  request_type_id: number | null
  request_type_name: string | null
  category: string | null
  customer_type: string | null
  priority: string | null
  department_id: number
  department_name: string
  assigned_user_id: number | null
  assigned_user_name: string | null
  is_active: boolean
}

type RuleForm = Omit<Rule, 'id' | 'request_type_name' | 'department_name' | 'assigned_user_name'>

export function AssignmentRulesPage() {
  const { tr, lang } = useI18n()
  const toast = useToast()
  const { data, error, loading, reload } = useApi<Rule[]>('/admin/assignment-rules')
  const settings = useApi<{ key: string; value: unknown }[]>('/admin/settings')
  const autoEnabled = settings.data?.find((s) => s.key === 'assignment.auto_enabled')?.value === true
  const [editing, setEditing] = useState<Rule | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Rule | null>(null)

  async function setAuto(v: boolean) {
    try {
      await api.put('/admin/settings/assignment.auto_enabled', { value: v })
      settings.reload()
      toast.success(v ? tr('เปิดการมอบหมายอัตโนมัติแล้ว', 'Auto-assignment enabled') : tr('ปิดการมอบหมายอัตโนมัติแล้ว', 'Auto-assignment disabled'))
    } catch (e) {
      toast.error((e as ApiError).message)
    }
  }

  async function remove() {
    if (!deleting) return
    try {
      await api.delete(`/admin/assignment-rules/${deleting.id}`)
      setDeleting(null)
      reload()
    } catch (e) {
      toast.error((e as ApiError).message)
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={tr('กฎการมอบหมายงานอัตโนมัติ', 'Automatic assignment rules')}
        subtitle={tr('ตรวจตามลำดับ กฎแรกที่ตรงเงื่อนไขจะถูกใช้ เงื่อนไขว่าง = ทุกค่า', 'Evaluated in order; the first matching rule wins. Empty condition = any value.')}
        actions={
          <button type="button" className="btn-primary" onClick={() => setEditing('new')}>
            + {tr('เพิ่มกฎ', 'Add rule')}
          </button>
        }
      />
      <div className="card flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <p className="font-medium text-navy-900">{tr('การมอบหมายงานอัตโนมัติ', 'Automatic assignment')}</p>
          <p className="text-sm text-slate-500">
            {tr('เมื่อปิด ระบบส่ง Ticket ไปยังแผนกเริ่มต้นของประเภทคำขอเท่านั้น', 'When off, tickets go to the request type’s default department only.')}
          </p>
        </div>
        <Toggle checked={autoEnabled} onChange={setAuto} label={autoEnabled ? tr('เปิด', 'On') : tr('ปิด', 'Off')} disabled={!settings.data} />
      </div>
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      <div className="card overflow-x-auto">
        {!data && loading ? (
          <Loading />
        ) : data && data.length === 0 ? (
          <EmptyState title={tr('ยังไม่มีกฎ', 'No rules yet')} />
        ) : (
          <table className="table-base">
            <thead>
              <tr>
                <th>#</th>
                <th>{tr('ชื่อกฎ', 'Rule')}</th>
                <th>{tr('เงื่อนไข', 'Conditions')}</th>
                <th>{tr('ผลลัพธ์', 'Assign to')}</th>
                <th>{tr('สถานะ', 'Status')}</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.map((r) => (
                <tr key={r.id}>
                  <td>{r.sort_order}</td>
                  <td className="font-medium">{r.name}</td>
                  <td className="space-x-1 text-xs">
                    {r.request_type_name && <Badge color="blue">{r.request_type_name}</Badge>}
                    {r.category && <Badge color="indigo">{r.category}</Badge>}
                    {r.customer_type && <Badge color="violet">{label(CUSTOMER_TYPE_LABELS, r.customer_type, lang)}</Badge>}
                    {r.priority && <Badge color="orange">{label(PRIORITY_LABELS, r.priority, lang)}</Badge>}
                    {!r.request_type_name && !r.category && !r.customer_type && !r.priority && <span className="text-slate-400">{tr('ทุก Ticket', 'Any ticket')}</span>}
                  </td>
                  <td className="text-sm">
                    {r.department_name}
                    {r.assigned_user_name && <span className="text-slate-500"> → {r.assigned_user_name}</span>}
                  </td>
                  <td>
                    <Badge color={r.is_active ? 'green' : 'slate'}>{r.is_active ? tr('ใช้งาน', 'Active') : tr('ปิด', 'Off')}</Badge>
                  </td>
                  <td className="space-x-1 text-right whitespace-nowrap">
                    <button type="button" className="btn-secondary px-2.5 py-1 text-xs" onClick={() => setEditing(r)}>
                      {tr('แก้ไข', 'Edit')}
                    </button>
                    <button type="button" className="btn-secondary px-2.5 py-1 text-xs text-red-700" onClick={() => setDeleting(r)}>
                      {tr('ลบ', 'Delete')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {editing && (
        <RuleDialog
          rule={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
      <ConfirmDialog
        open={!!deleting}
        danger
        title={tr('ลบกฎ', 'Delete rule')}
        message={deleting?.name}
        confirmLabel={tr('ลบ', 'Delete')}
        onCancel={() => setDeleting(null)}
        onConfirm={remove}
      />
    </div>
  )
}

function RuleDialog({ rule, onClose, onSaved }: { rule: Rule | null; onClose: () => void; onSaved: () => void }) {
  const { tr, pick, lang } = useI18n()
  const { lookups } = useLookups()
  const [f, setF] = useState<RuleForm>({
    name: rule?.name ?? '',
    sort_order: rule?.sort_order ?? 100,
    request_type_id: rule?.request_type_id ?? null,
    category: rule?.category ?? null,
    customer_type: rule?.customer_type ?? null,
    priority: rule?.priority ?? null,
    department_id: rule?.department_id ?? lookups?.departments[0]?.id ?? 0,
    assigned_user_id: rule?.assigned_user_id ?? null,
    is_active: rule?.is_active ?? true,
  })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const users = (lookups?.users ?? []).filter((u) => u.role === 'ADMIN' || u.department_ids.includes(f.department_id))

  async function save() {
    setBusy(true)
    setErr(null)
    try {
      const body = { ...f, category: f.category || null }
      if (rule) await api.put(`/admin/assignment-rules/${rule.id}`, body)
      else await api.post('/admin/assignment-rules', body)
      onSaved()
    } catch (e) {
      setErr((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }
  const num = (v: string) => (v ? Number(v) : null)
  return (
    <Modal
      open
      title={rule ? tr('แก้ไขกฎ', 'Edit rule') : tr('เพิ่มกฎ', 'Add rule')}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            {tr('ยกเลิก', 'Cancel')}
          </button>
          <button type="button" className="btn-primary" onClick={save} disabled={busy || !f.name || !f.department_id}>
            {busy && <Spinner className="h-4 w-4" />} {tr('บันทึก', 'Save')}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="grid grid-cols-[1fr_100px] gap-3">
          <label className="block">
            <span className="label">{tr('ชื่อกฎ', 'Rule name')}</span>
            <input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          </label>
          <label className="block">
            <span className="label">{tr('ลำดับ', 'Order')}</span>
            <input className="input" type="number" value={f.sort_order} onChange={(e) => setF({ ...f, sort_order: Number(e.target.value) })} />
          </label>
        </div>
        <p className="text-xs font-semibold text-slate-500 uppercase">{tr('เงื่อนไข', 'Conditions')}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="label">{tr('ประเภทคำขอ', 'Request type')}</span>
            <select className="input" value={f.request_type_id ?? ''} onChange={(e) => setF({ ...f, request_type_id: num(e.target.value) })}>
              <option value="">{tr('ทุกประเภท', 'Any')}</option>
              {lookups?.request_types.map((r) => (
                <option key={r.id} value={r.id}>
                  {pick(r, 'name')}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">{tr('หมวดสินค้า/อุปกรณ์ (ค่า category)', 'Product/equipment category')}</span>
            <input className="input" placeholder="e.g. MEDICAL_DEVICE" value={f.category ?? ''} onChange={(e) => setF({ ...f, category: e.target.value.toUpperCase() || null })} />
          </label>
          <label className="block">
            <span className="label">{tr('ประเภทลูกค้า', 'Customer type')}</span>
            <select className="input" value={f.customer_type ?? ''} onChange={(e) => setF({ ...f, customer_type: e.target.value || null })}>
              <option value="">{tr('ทุกประเภท', 'Any')}</option>
              {Object.keys(CUSTOMER_TYPE_LABELS).map((c) => (
                <option key={c} value={c}>
                  {label(CUSTOMER_TYPE_LABELS, c, lang)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">{tr('ความสำคัญ', 'Priority')}</span>
            <select className="input" value={f.priority ?? ''} onChange={(e) => setF({ ...f, priority: e.target.value || null })}>
              <option value="">{tr('ทุกระดับ', 'Any')}</option>
              {Object.keys(PRIORITY_LABELS).map((p) => (
                <option key={p} value={p}>
                  {label(PRIORITY_LABELS, p, lang)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="text-xs font-semibold text-slate-500 uppercase">{tr('มอบหมายให้', 'Assign to')}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="label">{tr('แผนก', 'Department')}</span>
            <select className="input" value={f.department_id} onChange={(e) => setF({ ...f, department_id: Number(e.target.value), assigned_user_id: null })}>
              {lookups?.departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {pick(d, 'name')}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">{tr('ผู้รับผิดชอบ (ไม่บังคับ)', 'Staff (optional)')}</span>
            <select className="input" value={f.assigned_user_id ?? ''} onChange={(e) => setF({ ...f, assigned_user_id: num(e.target.value) })}>
              <option value="">—</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Toggle checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} label={tr('ใช้งานกฎนี้', 'Rule active')} />
        {err && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{err}</p>}
      </div>
    </Modal>
  )
}
