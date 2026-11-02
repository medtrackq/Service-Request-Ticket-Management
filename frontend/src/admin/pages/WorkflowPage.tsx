import { useEffect, useState } from 'react'
import { ApiError, api } from '../../api/client'
import { useToast } from '../../components/Toast'
import { ErrorBox, Loading, SectionCard, Spinner, StatusBadge, cx } from '../../components/ui'
import { useI18n } from '../../i18n'
import { PageHeader } from '../AdminLayout'
import { useLookups } from '../auth'
import { useApi } from '../useApi'

interface Status {
  code: string
  name_th: string
  name_en: string
  category: string
  is_terminal: boolean
  color: string
  sort_order: number
}
interface Transition {
  from_status: string
  to_status: string
  allowed_roles: string[]
  requires_comment: boolean
  is_active: boolean
}

const COLORS = ['blue', 'indigo', 'violet', 'amber', 'orange', 'yellow', 'green', 'slate', 'red']
const ROLES = ['ADMIN', 'MANAGER', 'STAFF'] as const

export function WorkflowPage() {
  const { tr, lang } = useI18n()
  const toast = useToast()
  const { reload: reloadLookups } = useLookups()
  const { data, error, loading, reload } = useApi<{ statuses: Status[]; transitions: Transition[] }>('/admin/workflow')
  const [matrix, setMatrix] = useState<Record<string, Transition>>({})
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!data) return
    setMatrix(Object.fromEntries(data.transitions.map((t) => [`${t.from_status}>${t.to_status}`, t])))
    setDirty(false)
  }, [data])

  if (error) return <ErrorBox message={error.message} onRetry={reload} />
  if (!data || loading) return <Loading />
  const statuses = data.statuses

  function toggleCell(from: string, to: string) {
    const k = `${from}>${to}`
    setMatrix((m) => {
      const n = { ...m }
      if (n[k]) delete n[k]
      else n[k] = { from_status: from, to_status: to, allowed_roles: ['ADMIN', 'MANAGER', 'STAFF'], requires_comment: false, is_active: true }
      return n
    })
    setDirty(true)
  }
  function patchCell(k: string, patch: Partial<Transition>) {
    setMatrix((m) => ({ ...m, [k]: { ...m[k], ...patch } }))
    setDirty(true)
  }

  async function saveTransitions() {
    setBusy(true)
    try {
      await api.put('/admin/workflow/transitions', { transitions: Object.values(matrix) })
      toast.success(tr('บันทึก Workflow แล้ว', 'Workflow saved'))
      reload()
    } catch (e) {
      toast.error((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  async function saveStatus(s: Status) {
    try {
      await api.patch(`/admin/workflow/statuses/${s.code}`, { name_th: s.name_th, name_en: s.name_en, color: s.color })
      toast.success(tr('บันทึกแล้ว', 'Saved'))
      reloadLookups()
    } catch (e) {
      toast.error((e as ApiError).message)
    }
  }

  const name = (code: string) => {
    const s = statuses.find((x) => x.code === code)
    return s ? (lang === 'en' ? s.name_en : s.name_th) : code
  }

  return (
    <div className="space-y-5">
      <PageHeader title={tr('Workflow สถานะ', 'Status workflow')} subtitle={tr('กำหนดชื่อสถานะ และการเปลี่ยนสถานะที่อนุญาตตามบทบาท', 'Status names and allowed transitions per role')} />
      <SectionCard title={tr('สถานะ', 'Statuses')}>
        <StatusEditor statuses={statuses} onSave={saveStatus} />
      </SectionCard>
      <SectionCard
        title={tr('การเปลี่ยนสถานะที่อนุญาต (แถว = จาก, คอลัมน์ = ไป)', 'Allowed transitions (row = from, column = to)')}
        actions={
          <button type="button" className="btn-primary" disabled={!dirty || busy} onClick={saveTransitions}>
            {busy && <Spinner className="h-4 w-4" />} {tr('บันทึก Workflow', 'Save workflow')}
          </button>
        }
      >
        <p className="mb-3 text-xs text-slate-500">
          {tr(
            'คลิกช่องเพื่อเปิด/ปิด แล้วเลือกบทบาท (A=ผู้ดูแล, M=ผู้จัดการ, S=เจ้าหน้าที่) และ "บังคับระบุเหตุผล" (✎) Ticket ไม่จำเป็นต้องผ่านทุกสถานะ',
            'Click a cell to enable/disable, then choose roles (A=Admin, M=Manager, S=Staff) and ✎ = reason required. Tickets need not pass through every status.',
          )}
        </p>
        <div className="overflow-x-auto">
          <table className="border-collapse text-xs">
            <thead>
              <tr>
                <th className="sticky left-0 bg-white p-2 text-left">{tr('จาก \\ ไป', 'From \\ To')}</th>
                {statuses.map((s) => (
                  <th key={s.code} className="min-w-[92px] p-2 text-center font-medium text-slate-600">
                    {name(s.code)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {statuses.map((from) => (
                <tr key={from.code} className="border-t border-slate-100">
                  <th className="sticky left-0 bg-white p-2 text-left font-medium whitespace-nowrap text-slate-700">{name(from.code)}</th>
                  {statuses.map((to) => {
                    const k = `${from.code}>${to.code}`
                    const t = matrix[k]
                    if (from.code === to.code) return <td key={k} className="bg-slate-50 p-1" />
                    return (
                      <td key={k} className={cx('p-1 text-center align-top', t ? 'bg-brand-50' : '')}>
                        <button
                          type="button"
                          onClick={() => toggleCell(from.code, to.code)}
                          className={cx('h-6 w-6 rounded border text-[11px]', t ? 'border-brand-500 bg-brand-600 text-white' : 'border-slate-300 bg-white text-transparent hover:border-brand-400')}
                          aria-label={`${from.code} → ${to.code}`}
                          aria-pressed={!!t}
                        >
                          ✓
                        </button>
                        {t && (
                          <div className="mt-1 flex justify-center gap-0.5">
                            {ROLES.map((r) => (
                              <button
                                key={r}
                                type="button"
                                title={r}
                                onClick={() =>
                                  patchCell(k, {
                                    allowed_roles: t.allowed_roles.includes(r) ? t.allowed_roles.filter((x) => x !== r) : [...t.allowed_roles, r],
                                  })
                                }
                                className={cx('h-5 w-5 rounded text-[10px] font-bold', t.allowed_roles.includes(r) ? 'bg-navy-800 text-white' : 'bg-slate-200 text-slate-500')}
                              >
                                {r[0]}
                              </button>
                            ))}
                            <button
                              type="button"
                              title={tr('บังคับระบุเหตุผล', 'Reason required')}
                              onClick={() => patchCell(k, { requires_comment: !t.requires_comment })}
                              className={cx('h-5 w-5 rounded text-[10px]', t.requires_comment ? 'bg-amber-500 text-white' : 'bg-slate-200 text-slate-500')}
                            >
                              ✎
                            </button>
                          </div>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {Object.values(matrix).some((t) => t.allowed_roles.length === 0) && (
          <p className="mt-2 text-sm text-red-600">{tr('ทุก Transition ต้องมีอย่างน้อย 1 บทบาท', 'Each transition needs at least one role')}</p>
        )}
      </SectionCard>
    </div>
  )
}

function StatusEditor({ statuses, onSave }: { statuses: Status[]; onSave: (s: Status) => void }) {
  const { tr } = useI18n()
  const [rows, setRows] = useState(statuses)
  useEffect(() => setRows(statuses), [statuses])
  return (
    <div className="overflow-x-auto">
      <table className="table-base">
        <thead>
          <tr>
            <th>{tr('รหัส', 'Code')}</th>
            <th>{tr('ชื่อ (ไทย)', 'Thai')}</th>
            <th>{tr('ชื่อ (อังกฤษ)', 'English')}</th>
            <th>{tr('กลุ่ม', 'Category')}</th>
            <th>{tr('สี', 'Colour')}</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((s, i) => (
            <tr key={s.code}>
              <td className="font-mono text-xs">{s.code}</td>
              <td>
                <input className="input py-1.5 text-sm" value={s.name_th} onChange={(e) => setRows(rows.map((r, j) => (j === i ? { ...r, name_th: e.target.value } : r)))} />
              </td>
              <td>
                <input className="input py-1.5 text-sm" value={s.name_en} onChange={(e) => setRows(rows.map((r, j) => (j === i ? { ...r, name_en: e.target.value } : r)))} />
              </td>
              <td className="text-xs">{s.category}</td>
              <td>
                <div className="flex items-center gap-2">
                  <select className="input py-1.5 text-sm" value={s.color} onChange={(e) => setRows(rows.map((r, j) => (j === i ? { ...r, color: e.target.value } : r)))}>
                    {COLORS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <StatusBadge status={s} />
                </div>
              </td>
              <td>
                <button type="button" className="btn-secondary px-2.5 py-1 text-xs" onClick={() => onSave(s)}>
                  {tr('บันทึก', 'Save')}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
