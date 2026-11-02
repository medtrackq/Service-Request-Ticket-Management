import { useEffect, useState } from 'react'
import { ApiError, api } from '../../api/client'
import { useToast } from '../../components/Toast'
import { ErrorBox, Loading, PriorityBadge, Spinner, Toggle } from '../../components/ui'
import { useI18n } from '../../i18n'
import { PageHeader } from '../AdminLayout'
import { useApi } from '../useApi'

interface Setting {
  key: string
  value: unknown
  default: unknown
  description: string
}

type Targets = Record<string, { first_response_hours: number | null; resolution_hours: number | null }>

const GROUPS: { prefix: string; th: string; en: string }[] = [
  { prefix: 'portal.', th: 'พอร์ทัลลูกค้า', en: 'Customer portal' },
  { prefix: 'privacy.', th: 'ความเป็นส่วนตัว (PDPA)', en: 'Privacy (PDPA)' },
  { prefix: 'service_targets', th: 'เป้าหมายการให้บริการ', en: 'Service targets' },
  { prefix: 'notifications.', th: 'การแจ้งเตือน', en: 'Notifications' },
  { prefix: 'assignment.', th: 'การมอบหมายงาน', en: 'Assignment' },
  { prefix: 'access.', th: 'สิทธิ์การเข้าถึง', en: 'Access' },
  { prefix: 'tracking.', th: 'การติดตามสถานะ', en: 'Tracking' },
  { prefix: 'line.', th: 'LINE', en: 'LINE' },
  { prefix: 'audit.', th: 'Audit Log', en: 'Audit log' },
]

export function SettingsPage() {
  const { tr } = useI18n()
  const { data, error, loading, reload } = useApi<Setting[]>('/admin/settings')
  if (error) return <ErrorBox message={error.message} onRetry={reload} />
  if (!data) return loading ? <Loading /> : null
  return (
    <div className="space-y-5">
      <PageHeader title={tr('ตั้งค่าระบบ', 'System settings')} subtitle={tr('ค่าที่บันทึกจะมีผลทันที', 'Changes take effect immediately')} />
      {GROUPS.map((g) => {
        const items = data.filter((s) => s.key.startsWith(g.prefix))
        if (!items.length) return null
        return (
          <section key={g.prefix} className="card">
            <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-navy-900">{tr(g.th, g.en)}</h2>
            <div className="divide-y divide-slate-100">
              {items.map((s) => (
                <SettingRow key={s.key} setting={s} />
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}

function SettingRow({ setting }: { setting: Setting }) {
  const { tr } = useI18n()
  const toast = useToast()
  const [value, setValue] = useState<unknown>(setting.value)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => setValue(setting.value), [setting.value])
  const dirty = JSON.stringify(value) !== JSON.stringify(setting.value)

  async function save(v: unknown = value) {
    setBusy(true)
    setErr(null)
    try {
      await api.put(`/admin/settings/${encodeURIComponent(setting.key)}`, { value: v })
      setting.value = v
      toast.success(tr('บันทึกแล้ว', 'Saved'))
    } catch (e) {
      setErr((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  const def = setting.default
  let editor: React.ReactNode
  if (typeof def === 'boolean') {
    editor = (
      <Toggle
        checked={value === true}
        disabled={busy}
        onChange={(v) => {
          setValue(v)
          void save(v)
        }}
      />
    )
  } else if (typeof def === 'number') {
    editor = <input type="number" min={0} className="input w-36" value={String(value ?? 0)} onChange={(e) => setValue(Number(e.target.value))} />
  } else if (typeof def === 'string') {
    const long = setting.key.includes('notice') || String(def).length > 80
    editor = long ? (
      <textarea className="input min-h-40 text-sm" value={String(value ?? '')} onChange={(e) => setValue(e.target.value)} />
    ) : (
      <input className="input" value={String(value ?? '')} onChange={(e) => setValue(e.target.value)} />
    )
  } else if (setting.key === 'service_targets') {
    editor = <TargetsEditor value={(value as Targets) ?? {}} onChange={setValue} />
  } else {
    editor = <code className="text-xs">{JSON.stringify(value)}</code>
  }

  return (
    <div className="grid gap-2 px-4 py-3 md:grid-cols-[minmax(0,320px)_minmax(0,1fr)] md:gap-6">
      <div>
        <p className="font-mono text-xs text-slate-500">{setting.key}</p>
        <p className="text-sm text-slate-700">{setting.description}</p>
      </div>
      <div className="min-w-0 space-y-2">
        {editor}
        {typeof def !== 'boolean' && (
          <div className="flex items-center gap-2">
            <button type="button" className="btn-primary px-3 py-1.5 text-xs" onClick={() => save()} disabled={!dirty || busy}>
              {busy && <Spinner className="h-3 w-3" />} {tr('บันทึก', 'Save')}
            </button>
            {dirty && (
              <button type="button" className="btn-ghost px-3 py-1.5 text-xs" onClick={() => setValue(setting.value)}>
                {tr('ยกเลิก', 'Revert')}
              </button>
            )}
          </div>
        )}
        {err && <p className="text-sm text-red-600">{err}</p>}
      </div>
    </div>
  )
}

function TargetsEditor({ value, onChange }: { value: Targets; onChange: (v: Targets) => void }) {
  const { tr } = useI18n()
  const set = (p: string, k: 'first_response_hours' | 'resolution_hours', v: string) =>
    onChange({ ...value, [p]: { ...value[p], [k]: v === '' ? null : Number(v) } })
  return (
    <div className="overflow-x-auto">
      <table className="table-base">
        <thead>
          <tr>
            <th>{tr('ความสำคัญ', 'Priority')}</th>
            <th>{tr('ตอบกลับครั้งแรก (ชม.)', 'First response (h)')}</th>
            <th>{tr('แก้ไขเสร็จ (ชม.)', 'Resolution (h)')}</th>
          </tr>
        </thead>
        <tbody>
          {['URGENT', 'HIGH', 'NORMAL', 'LOW'].map((p) => (
            <tr key={p}>
              <td>
                <PriorityBadge priority={p} />
              </td>
              <td>
                <input type="number" min={1} className="input w-28 py-1.5" value={value[p]?.first_response_hours ?? ''} onChange={(e) => set(p, 'first_response_hours', e.target.value)} />
              </td>
              <td>
                <input type="number" min={1} className="input w-28 py-1.5" value={value[p]?.resolution_hours ?? ''} onChange={(e) => set(p, 'resolution_hours', e.target.value)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-xs text-slate-500">{tr('ว่าง = ไม่กำหนดเป้าหมาย / ไม่คำนวณวันครบกำหนดอัตโนมัติ', 'Empty = no target / no automatic due date')}</p>
    </div>
  )
}
