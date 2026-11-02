import { useState } from 'react'
import { ApiError, api } from '../../api/client'
import { useToast } from '../../components/Toast'
import { Badge, ErrorBox, FieldError, Loading, Modal, Spinner, Toggle } from '../../components/ui'
import { useI18n } from '../../i18n'
import { PageHeader } from '../AdminLayout'
import { useLookups } from '../auth'
import { useApi } from '../useApi'

interface Dept {
  id: number
  code: string
  name_th: string
  name_en: string
  email: string | null
  is_active: boolean
  sort_order: number
  member_count: number
  open_tickets: number
}

export function DepartmentsPage() {
  const { tr } = useI18n()
  const toast = useToast()
  const { reload: reloadLookups } = useLookups()
  const { data, error, loading, reload } = useApi<Dept[]>('/admin/departments')
  const [editing, setEditing] = useState<Dept | 'new' | null>(null)
  return (
    <div className="space-y-4">
      <PageHeader
        title={tr('แผนก', 'Departments')}
        actions={
          <button type="button" className="btn-primary" onClick={() => setEditing('new')}>
            + {tr('เพิ่มแผนก', 'Add department')}
          </button>
        }
      />
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      <div className="card overflow-x-auto">
        {!data && loading ? (
          <Loading />
        ) : (
          <table className="table-base">
            <thead>
              <tr>
                <th>{tr('รหัส', 'Code')}</th>
                <th>{tr('ชื่อ', 'Name')}</th>
                <th>{tr('อีเมลแผนก', 'Shared mailbox')}</th>
                <th className="text-right">{tr('สมาชิก', 'Members')}</th>
                <th className="text-right">{tr('งานที่เปิดอยู่', 'Open tickets')}</th>
                <th>{tr('สถานะ', 'Status')}</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data?.map((d) => (
                <tr key={d.id}>
                  <td className="font-mono text-xs">{d.code}</td>
                  <td>
                    <p className="font-medium">{d.name_th}</p>
                    <p className="text-xs text-slate-500">{d.name_en}</p>
                  </td>
                  <td className="text-xs">{d.email ?? '-'}</td>
                  <td className="text-right">{d.member_count}</td>
                  <td className="text-right">{d.open_tickets}</td>
                  <td>
                    <Badge color={d.is_active ? 'green' : 'slate'}>{d.is_active ? tr('ใช้งาน', 'Active') : tr('ปิด', 'Inactive')}</Badge>
                  </td>
                  <td className="text-right">
                    <button type="button" className="btn-secondary px-2.5 py-1 text-xs" onClick={() => setEditing(d)}>
                      {tr('แก้ไข', 'Edit')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {editing && (
        <DeptDialog
          dept={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
            reloadLookups()
            toast.success(tr('บันทึกแล้ว', 'Saved'))
          }}
        />
      )}
    </div>
  )
}

function DeptDialog({ dept, onClose, onSaved }: { dept: Dept | null; onClose: () => void; onSaved: () => void }) {
  const { tr } = useI18n()
  const [f, setF] = useState({
    code: dept?.code ?? '',
    name_th: dept?.name_th ?? '',
    name_en: dept?.name_en ?? '',
    email: dept?.email ?? '',
    is_active: dept?.is_active ?? true,
    sort_order: dept?.sort_order ?? 10,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  async function save() {
    setBusy(true)
    setErrors({})
    try {
      const body = { ...f, email: f.email || null, sort_order: Number(f.sort_order) || 0 }
      if (dept) {
        const { code: _c, ...rest } = body
        void _c
        await api.patch(`/admin/departments/${dept.id}`, rest)
      } else await api.post('/admin/departments', body)
      onSaved()
    } catch (e) {
      const ae = e as ApiError
      setErrors({ ...ae.fields, form: ae.message })
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal
      open
      title={dept ? tr('แก้ไขแผนก', 'Edit department') : tr('เพิ่มแผนก', 'Add department')}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            {tr('ยกเลิก', 'Cancel')}
          </button>
          <button type="button" className="btn-primary" onClick={save} disabled={busy}>
            {busy && <Spinner className="h-4 w-4" />} {tr('บันทึก', 'Save')}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        {!dept && (
          <label className="block">
            <span className="label">{tr('รหัส (A-Z, 0-9, _)', 'Code (A-Z, 0-9, _)')}</span>
            <input className="input font-mono uppercase" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase() })} />
            <FieldError message={errors.code} />
          </label>
        )}
        <label className="block">
          <span className="label">{tr('ชื่อภาษาไทย', 'Thai name')}</span>
          <input className="input" value={f.name_th} onChange={(e) => setF({ ...f, name_th: e.target.value })} />
        </label>
        <label className="block">
          <span className="label">{tr('ชื่อภาษาอังกฤษ', 'English name')}</span>
          <input className="input" value={f.name_en} onChange={(e) => setF({ ...f, name_en: e.target.value })} />
        </label>
        <label className="block">
          <span className="label">{tr('อีเมลแผนก (แจ้งเตือน Ticket ใหม่)', 'Shared mailbox (new ticket alerts)')}</span>
          <input className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
          <FieldError message={errors.email} />
        </label>
        <label className="block">
          <span className="label">{tr('ลำดับการแสดง', 'Sort order')}</span>
          <input className="input" type="number" value={f.sort_order} onChange={(e) => setF({ ...f, sort_order: Number(e.target.value) })} />
        </label>
        <Toggle checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} label={tr('ใช้งาน', 'Active')} />
        {errors.form && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{errors.form}</p>}
      </div>
    </Modal>
  )
}
