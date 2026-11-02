import { useState } from 'react'
import { ApiError, api } from '../../api/client'
import type { FormFieldDef } from '../../api/types'
import { RequestTypeIcon } from '../../components/Icons'
import { useToast } from '../../components/Toast'
import { Badge, CopyButton, ErrorBox, Loading, Modal, Spinner, Toggle } from '../../components/ui'
import { PRIORITY_LABELS, useI18n } from '../../i18n'
import { formatDateTime } from '../../lib/dates'
import { PageHeader } from '../AdminLayout'
import { useLookups } from '../auth'
import { useApi } from '../useApi'

interface RT {
  id: number
  code: string
  slug: string
  ticket_prefix: string
  name_th: string
  name_en: string
  description_th: string | null
  description_en: string | null
  icon: string
  default_department_id: number
  default_department_name: string
  default_priority: string
  is_active: boolean
  sort_order: number
  active_form_id: number | null
  active_form_version: number | null
  portal_url: string
}

interface FormVersion {
  id: number
  version: number
  title_th: string
  title_en: string
  subject_template: string
  is_active: boolean
  created_at: string
  fields: (FormFieldDef & { sort_order: number })[]
}

export function RequestTypesPage() {
  const { tr } = useI18n()
  const { data, error, loading, reload } = useApi<RT[]>('/admin/request-types')
  const [editing, setEditing] = useState<RT | null>(null)
  const [forms, setForms] = useState<RT | null>(null)
  return (
    <div className="space-y-4">
      <PageHeader
        title={tr('ประเภทคำขอ & แบบฟอร์ม', 'Request types & forms')}
        subtitle={tr('ตั้งค่าแผนกเริ่มต้น ความสำคัญ และ URL สำหรับ LINE Rich Menu', 'Default department, priority and LINE Rich Menu URLs')}
      />
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      {!data && loading && <Loading />}
      <div className="grid gap-4 lg:grid-cols-2">
        {data?.map((r) => (
          <section key={r.id} className="card p-4">
            <div className="flex items-start gap-3">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-navy-900 text-white">
                <RequestTypeIcon icon={r.icon} size={22} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold text-navy-900">{r.name_th}</h2>
                  <Badge color="blue">{r.code}</Badge>
                  <Badge color="slate">BUC-{r.ticket_prefix}-YYYY-NNNNN</Badge>
                  {!r.is_active && <Badge color="red">{tr('ปิดใช้งาน', 'Inactive')}</Badge>}
                </div>
                <p className="text-xs text-slate-500">{r.name_en}</p>
              </div>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <div>
                <dt className="text-xs text-slate-500">{tr('แผนกเริ่มต้น', 'Default department')}</dt>
                <dd>{r.default_department_name}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">{tr('ความสำคัญเริ่มต้น', 'Default priority')}</dt>
                <dd>{PRIORITY_LABELS[r.default_priority]?.th ?? r.default_priority}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">{tr('แบบฟอร์มที่ใช้งาน', 'Active form')}</dt>
                <dd>v{r.active_form_version ?? '-'}</dd>
              </div>
            </dl>
            <div className="mt-3 rounded-lg bg-slate-50 p-2.5">
              <p className="text-xs font-medium text-slate-500">LINE Rich Menu URL</p>
              <div className="mt-1 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate text-xs text-slate-800">{r.portal_url}</code>
                <CopyButton text={r.portal_url} className="px-2.5 py-1 text-xs" />
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={() => setEditing(r)}>
                {tr('แก้ไขการตั้งค่า', 'Edit settings')}
              </button>
              <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={() => setForms(r)}>
                {tr('ดู / แก้ไขแบบฟอร์ม', 'View / edit form')}
              </button>
            </div>
          </section>
        ))}
      </div>
      {editing && <RTDialog rt={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload() }} />}
      {forms && <FormsDialog rt={forms} onClose={() => setForms(null)} onPublished={reload} />}
    </div>
  )
}

function RTDialog({ rt, onClose, onSaved }: { rt: RT; onClose: () => void; onSaved: () => void }) {
  const { tr, pick } = useI18n()
  const { lookups } = useLookups()
  const toast = useToast()
  const [f, setF] = useState({
    name_th: rt.name_th,
    name_en: rt.name_en,
    description_th: rt.description_th ?? '',
    description_en: rt.description_en ?? '',
    default_department_id: rt.default_department_id,
    default_priority: rt.default_priority,
    is_active: rt.is_active,
    sort_order: rt.sort_order,
  })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  async function save() {
    setBusy(true)
    setErr(null)
    try {
      await api.patch(`/admin/request-types/${rt.id}`, f)
      toast.success(tr('บันทึกแล้ว', 'Saved'))
      onSaved()
    } catch (e) {
      setErr((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal
      open
      title={`${tr('แก้ไขประเภทคำขอ', 'Edit request type')} ${rt.code}`}
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
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="label">{tr('ชื่อ (ไทย)', 'Name (Thai)')}</span>
            <input className="input" value={f.name_th} onChange={(e) => setF({ ...f, name_th: e.target.value })} />
          </label>
          <label className="block">
            <span className="label">{tr('ชื่อ (อังกฤษ)', 'Name (English)')}</span>
            <input className="input" value={f.name_en} onChange={(e) => setF({ ...f, name_en: e.target.value })} />
          </label>
        </div>
        <label className="block">
          <span className="label">{tr('คำอธิบาย (ไทย)', 'Description (Thai)')}</span>
          <input className="input" value={f.description_th} onChange={(e) => setF({ ...f, description_th: e.target.value })} />
        </label>
        <label className="block">
          <span className="label">{tr('คำอธิบาย (อังกฤษ)', 'Description (English)')}</span>
          <input className="input" value={f.description_en} onChange={(e) => setF({ ...f, description_en: e.target.value })} />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="label">{tr('แผนกเริ่มต้น', 'Default department')}</span>
            <select className="input" value={f.default_department_id} onChange={(e) => setF({ ...f, default_department_id: Number(e.target.value) })}>
              {lookups?.departments.filter((d) => d.is_active).map((d) => (
                <option key={d.id} value={d.id}>
                  {pick(d, 'name')}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">{tr('ความสำคัญเริ่มต้น', 'Default priority')}</span>
            <select className="input" value={f.default_priority} onChange={(e) => setF({ ...f, default_priority: e.target.value })}>
              {Object.keys(PRIORITY_LABELS).map((p) => (
                <option key={p} value={p}>
                  {PRIORITY_LABELS[p].th} / {PRIORITY_LABELS[p].en}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Toggle checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} label={tr('เปิดให้ลูกค้าใช้งาน', 'Available on the portal')} />
        {err && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{err}</p>}
      </div>
    </Modal>
  )
}

function FormsDialog({ rt, onClose, onPublished }: { rt: RT; onClose: () => void; onPublished: () => void }) {
  const { tr, lang } = useI18n()
  const toast = useToast()
  const { data, error, reload } = useApi<FormVersion[]>(`/admin/request-types/${rt.id}/forms`)
  const [json, setJson] = useState<string | null>(null)
  const [problems, setProblems] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const active = data?.find((f) => f.is_active) ?? data?.[0]

  function startEdit() {
    if (!active) return
    const fields = active.fields.map(({ sort_order: _s, ...rest }) => {
      void _s
      return rest
    })
    setJson(
      JSON.stringify(
        { title_th: active.title_th, title_en: active.title_en, subject_template: active.subject_template, fields },
        null,
        2,
      ),
    )
    setProblems([])
  }

  async function publish() {
    if (json == null) return
    let body: unknown
    try {
      body = JSON.parse(json)
    } catch (e) {
      setProblems([`JSON: ${(e as Error).message}`])
      return
    }
    setBusy(true)
    setProblems([])
    try {
      const r = await api.post<{ version: number }>(`/admin/request-types/${rt.id}/forms`, body)
      toast.success(tr(`เผยแพร่แบบฟอร์มเวอร์ชัน ${r.version} แล้ว`, `Form version ${r.version} published`))
      setJson(null)
      reload()
      onPublished()
    } catch (e) {
      const ae = e as ApiError
      const list = (ae.detail?.problems as string[] | undefined) ?? Object.values(ae.fields)
      setProblems(list.length ? list : [ae.message])
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open wide title={`${tr('แบบฟอร์ม', 'Form')}: ${rt.name_th}`} onClose={onClose}>
      {error && <ErrorBox message={error.message} />}
      {!data ? (
        <Loading />
      ) : json == null ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-slate-600">
              {tr('เวอร์ชันที่ใช้งาน', 'Active version')}: <b>v{active?.version}</b> · {tr('หัวเรื่อง', 'Subject template')}: <code className="text-xs">{active?.subject_template}</code>
            </p>
            <button type="button" className="btn-primary px-3 py-1.5 text-xs" onClick={startEdit}>
              {tr('สร้างเวอร์ชันใหม่ (JSON)', 'New version (JSON)')}
            </button>
          </div>
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="table-base">
              <thead>
                <tr>
                  <th>key</th>
                  <th>{tr('ป้ายชื่อ', 'Label')}</th>
                  <th>{tr('ชนิด', 'Type')}</th>
                  <th>{tr('ส่วน', 'Section')}</th>
                  <th>{tr('บังคับ', 'Req.')}</th>
                  <th>maps_to</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {active?.fields.map((f) => (
                  <tr key={f.key}>
                    <td className="font-mono text-xs">{f.key}</td>
                    <td>
                      {f.label_th}
                      <p className="text-xs text-slate-500">{f.label_en}</p>
                    </td>
                    <td className="text-xs">
                      {f.field_type}
                      {f.options && <span className="text-slate-400"> ({f.options.length})</span>}
                    </td>
                    <td className="text-xs">{f.section}</td>
                    <td>{f.required ? '✓' : ''}</td>
                    <td className="font-mono text-xs">{f.maps_to ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-500">
            {tr('ประวัติเวอร์ชัน', 'Version history')}:{' '}
            {data.map((f) => `v${f.version}${f.is_active ? ' ✓' : ''} (${formatDateTime(f.created_at, lang)})`).join(' · ')}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
            {tr(
              'การเผยแพร่จะสร้างเวอร์ชันใหม่และใช้งานทันที Ticket เดิมยังอ้างอิงเวอร์ชันที่ใช้ตอนส่ง ต้องมีฟิลด์ maps_to: customer.name, contact.name, contact.phone, ticket.description และฟิลด์ไฟล์ได้ไม่เกิน 1 ฟิลด์',
              'Publishing creates and activates a new version; existing tickets keep their version. Required maps_to: customer.name, contact.name, contact.phone, ticket.description; at most one file field.',
            )}
          </p>
          <textarea className="input h-[50vh] font-mono text-xs" spellCheck={false} value={json} onChange={(e) => setJson(e.target.value)} />
          {problems.length > 0 && (
            <ul className="list-disc space-y-1 rounded-lg bg-red-50 p-3 pl-6 text-sm text-red-700">
              {problems.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          )}
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={() => setJson(null)}>
              {tr('ยกเลิก', 'Cancel')}
            </button>
            <button type="button" className="btn-primary" onClick={publish} disabled={busy}>
              {busy && <Spinner className="h-4 w-4" />} {tr('เผยแพร่เวอร์ชันใหม่', 'Publish new version')}
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
