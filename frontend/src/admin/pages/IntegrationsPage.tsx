import { useState, type FormEvent } from 'react'
import { ApiError, api } from '../../api/client'
import { useToast } from '../../components/Toast'
import { Badge, CopyButton, ErrorBox, Loading, SectionCard, Spinner } from '../../components/ui'
import { useI18n } from '../../i18n'
import { formatDateTime } from '../../lib/dates'
import { PageHeader } from '../AdminLayout'
import { useApi } from '../useApi'

interface IntegrationStatus {
  public_base_url: string
  line: {
    rich_menu_mode: string
    rich_menu: { code: string; label_th: string; label_en: string; url: string; is_active: boolean }[]
    tracking_url: string
    liff_login_configured: boolean
    messaging_api_configured: boolean
  }
  email: { smtp_configured: boolean; from: string }
  erpnext: { enabled: boolean; configured: boolean; status: string; mappings: number }
}

interface Mapping {
  id: number
  system: string
  local_entity_type: string
  local_id: string
  external_doctype: string
  external_name: string | null
  sync_status: string
  updated_at: string
}

interface IntegrationLogRow {
  id: number
  created_at: string
  system: string
  direction: string
  operation: string
  local_entity_type: string | null
  local_id: string | null
  external_doctype: string | null
  external_name: string | null
  status: string
  error: string | null
}

function Flag({ ok, on, off }: { ok: boolean; on: string; off: string }) {
  return <Badge color={ok ? 'green' : 'slate'}>{ok ? on : off}</Badge>
}

export function IntegrationsPage() {
  const { tr, lang } = useI18n()
  const toast = useToast()
  const { data, error, reload } = useApi<IntegrationStatus>('/admin/integrations')
  const mappings = useApi<{ total: number; items: Mapping[] }>('/admin/integrations/mappings')
  const logs = useApi<{ total: number; items: IntegrationLogRow[] }>('/admin/integrations/logs?page_size=20')
  const [form, setForm] = useState({ local_id: '', external_name: '' })
  const [busy, setBusy] = useState(false)

  async function saveMapping(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      await api.post('/admin/integrations/mappings', {
        local_entity_type: 'customer',
        local_id: form.local_id.trim(),
        external_doctype: 'Customer',
        external_name: form.external_name.trim() || null,
      })
      toast.success(tr('บันทึกการจับคู่แล้ว', 'Mapping saved'))
      setForm({ local_id: '', external_name: '' })
      mappings.reload()
      logs.reload()
    } catch (err) {
      toast.error((err as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  if (error) return <ErrorBox message={error.message} onRetry={reload} />
  if (!data) return <Loading />
  const on = tr('ตั้งค่าแล้ว', 'Configured')
  const off = tr('ยังไม่ตั้งค่า', 'Not configured')

  return (
    <div className="space-y-5">
      <PageHeader title={tr('การเชื่อมต่อระบบ', 'Integrations')} subtitle={`Public base URL: ${data.public_base_url}`} />

      <SectionCard title="LINE Official Account — Rich Menu (URL actions)">
        <p className="mb-3 text-sm text-slate-600">
          {tr(
            'นำ URL ด้านล่างไปตั้งค่าเป็น Action แบบ "ลิงก์" ของปุ่ม Rich Menu ทั้ง 6 ปุ่มใน LINE Official Account Manager (ไม่ต้องใช้ Messaging API)',
            'Use these URLs as "Link" actions for the six Rich Menu buttons in LINE Official Account Manager (no Messaging API required).',
          )}
        </p>
        <div className="overflow-x-auto">
          <table className="table-base">
            <thead>
              <tr>
                <th>{tr('ปุ่ม', 'Button')}</th>
                <th>URL</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.line.rich_menu.map((r) => (
                <tr key={r.code}>
                  <td className="whitespace-nowrap">
                    {lang === 'en' ? r.label_en : r.label_th} {!r.is_active && <Badge color="red">{tr('ปิด', 'off')}</Badge>}
                  </td>
                  <td className="font-mono text-xs break-all">{r.url}</td>
                  <td>
                    <CopyButton text={r.url} className="px-2.5 py-1 text-xs" />
                  </td>
                </tr>
              ))}
              <tr>
                <td>{tr('ติดตามสถานะ', 'Tracking page')}</td>
                <td className="font-mono text-xs break-all">{data.line.tracking_url}</td>
                <td>
                  <CopyButton text={data.line.tracking_url} className="px-2.5 py-1 text-xs" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div className="rounded-lg border border-slate-200 p-3">
            <p className="font-medium">LINE Login / LIFF</p>
            <Flag ok={data.line.liff_login_configured} on={on} off={off} />
            <p className="mt-1 text-xs text-slate-500">
              {tr('ใช้ยืนยันตัวตนลูกค้าผ่าน ID token (ตรวจสอบฝั่งเซิร์ฟเวอร์) — ทางเลือก', 'Optional: verifies customer identity via server-side ID token verification')}
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 p-3">
            <p className="font-medium">LINE Messaging API</p>
            <Flag ok={data.line.messaging_api_configured} on={on} off={off} />
            <p className="mt-1 text-xs text-slate-500">{tr('สำหรับแจ้งเตือนลูกค้าทาง LINE ในอนาคต (ปิดไว้เป็นค่าเริ่มต้น)', 'Future customer push notifications (disabled by default)')}</p>
          </div>
        </div>
      </SectionCard>

      <div className="grid gap-5 lg:grid-cols-2">
        <SectionCard title={tr('อีเมล (SMTP)', 'E-mail (SMTP)')}>
          <Flag ok={data.email.smtp_configured} on={on} off={off} />
          <p className="mt-2 text-sm text-slate-600">From: {data.email.from}</p>
          {!data.email.smtp_configured && (
            <p className="mt-2 text-xs text-slate-500">
              {tr('ยังไม่ได้ตั้งค่า BUC_SMTP_HOST อีเมลจะถูกบันทึกเป็น SKIPPED ในบันทึกการส่งแจ้งเตือน', 'BUC_SMTP_HOST not set — e-mails are logged as SKIPPED.')}
            </p>
          )}
        </SectionCard>
        <SectionCard title="ERPNext">
          <div className="flex flex-wrap gap-2">
            <Badge color="slate">{tr('ยังไม่เปิดใช้งาน', 'Disabled')}</Badge>
            <Flag ok={data.erpnext.configured} on={tr('มีค่าการเชื่อมต่อ', 'Credentials set')} off={tr('ไม่มีค่าการเชื่อมต่อ', 'No credentials')} />
          </div>
          <p className="mt-2 text-sm text-slate-600">
            {tr('ยังไม่มีการซิงค์ข้อมูลกับ ERPNext ในเวอร์ชันนี้ (มีเฉพาะ Interface และตารางจับคู่ข้อมูล)', 'Not implemented in this version — interfaces and mapping tables only.')}
          </p>
          <p className="mt-1 text-xs text-slate-500">{data.erpnext.status}</p>
        </SectionCard>
      </div>

      <SectionCard title={tr('การจับคู่ลูกค้ากับ ERPNext Customer (บันทึกด้วยตนเอง)', 'Customer → ERPNext Customer mapping (manual)')}>
        <form onSubmit={saveMapping} className="mb-4 grid gap-3 sm:grid-cols-[160px_minmax(0,1fr)_auto]">
          <input className="input" placeholder={tr('รหัสลูกค้าในระบบ (ID)', 'Local customer ID')} inputMode="numeric" value={form.local_id} onChange={(e) => setForm({ ...form, local_id: e.target.value })} />
          <input className="input" placeholder={tr('ชื่อเอกสาร ERPNext Customer (เช่น CUST-00012)', 'ERPNext Customer name (e.g. CUST-00012)')} value={form.external_name} onChange={(e) => setForm({ ...form, external_name: e.target.value })} />
          <button type="submit" className="btn-primary" disabled={busy || !form.local_id}>
            {busy && <Spinner className="h-4 w-4" />} {tr('บันทึก', 'Save')}
          </button>
        </form>
        <p className="mb-3 text-xs text-slate-500">
          {tr('ดูรหัสลูกค้าได้ที่เมนู "ลูกค้า" การบันทึกนี้ไม่เรียก ERPNext จริง', 'Find customer IDs on the Customers page. Saving does not call ERPNext.')}
        </p>
        {mappings.data && mappings.data.items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="table-base">
              <thead>
                <tr>
                  <th>{tr('ข้อมูลในระบบ', 'Local')}</th>
                  <th>ERPNext</th>
                  <th>{tr('สถานะ', 'Status')}</th>
                  <th>{tr('อัปเดต', 'Updated')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {mappings.data.items.map((m) => (
                  <tr key={m.id}>
                    <td className="text-xs">
                      {m.local_entity_type} #{m.local_id}
                    </td>
                    <td className="text-xs">
                      {m.external_doctype}: <b>{m.external_name ?? '-'}</b>
                    </td>
                    <td>
                      <Badge color="blue">{m.sync_status}</Badge>
                    </td>
                    <td className="text-xs">{formatDateTime(m.updated_at, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-slate-500">{tr('ยังไม่มีการจับคู่', 'No mappings yet')}</p>
        )}
      </SectionCard>

      <SectionCard title={tr('บันทึกการเชื่อมต่อ (Integration log)', 'Integration log')}>
        {logs.data && logs.data.items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="table-base">
              <thead>
                <tr>
                  <th>{tr('เวลา', 'Time')}</th>
                  <th>{tr('ระบบ', 'System')}</th>
                  <th>{tr('การดำเนินการ', 'Operation')}</th>
                  <th>{tr('ข้อมูล', 'Record')}</th>
                  <th>{tr('สถานะ', 'Status')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.data.items.map((l) => (
                  <tr key={l.id}>
                    <td className="text-xs whitespace-nowrap">{formatDateTime(l.created_at, lang)}</td>
                    <td className="text-xs">
                      {l.system} · {l.direction}
                    </td>
                    <td className="font-mono text-xs">{l.operation}</td>
                    <td className="text-xs">
                      {l.local_entity_type} #{l.local_id} → {l.external_doctype} {l.external_name}
                    </td>
                    <td>
                      <Badge color={l.status === 'SUCCESS' ? 'green' : l.status === 'FAILED' ? 'red' : 'slate'}>{l.status}</Badge>
                      {l.error && <p className="text-xs text-red-700">{l.error}</p>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-slate-500">{tr('ยังไม่มีบันทึก', 'No entries yet')}</p>
        )}
      </SectionCard>
    </div>
  )
}
