import { useState } from 'react'
import { ApiError, api, queryString } from '../../api/client'
import { useToast } from '../../components/Toast'
import { Badge, EmptyState, ErrorBox, Loading, Modal, Pagination, Spinner, Toggle } from '../../components/ui'
import { CUSTOMER_TYPE_LABELS, label, useI18n } from '../../i18n'
import { formatDateTime } from '../../lib/dates'
import { PageHeader } from '../AdminLayout'
import { useApi } from '../useApi'

interface Customer {
  id: number
  code: string | null
  name: string
  customer_type: string
  tax_id: string | null
  address: string | null
  notes: string | null
  is_active: boolean
  ticket_count: number
  erpnext_customer: string | null
  created_at: string
}

interface Contact {
  id: number
  name: string
  department: string | null
  phone: string | null
  email: string | null
  line_verified: boolean
  anonymized_at: string | null
  created_at: string
}

export function CustomersPage() {
  const { tr, lang } = useI18n()
  const [q, setQ] = useState('')
  const [applied, setApplied] = useState('')
  const [page, setPage] = useState(1)
  const { data, error, loading, reload } = useApi<{ total: number; items: Customer[] }>(`/admin/customers${queryString({ q: applied, page, page_size: 50 })}`)
  const [editing, setEditing] = useState<Customer | null>(null)
  const [contactsFor, setContactsFor] = useState<Customer | null>(null)

  return (
    <div className="space-y-4">
      <PageHeader title={tr('ลูกค้า', 'Customers')} subtitle={tr('ข้อมูลหลักลูกค้าที่สร้างจากแบบฟอร์ม (จับคู่ตามชื่อหน่วยงาน)', 'Customer master data created from portal submissions (matched by organisation name)')} />
      <form
        className="flex max-w-lg gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          setPage(1)
          setApplied(q.trim())
        }}
      >
        <input className="input" placeholder={tr('ค้นหาชื่อหรือรหัสลูกค้า', 'Search name or code')} value={q} onChange={(e) => setQ(e.target.value)} />
        <button type="submit" className="btn-primary">
          {tr('ค้นหา', 'Search')}
        </button>
      </form>
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      <div className="card overflow-x-auto">
        {!data && loading ? (
          <Loading />
        ) : !data?.items.length ? (
          <EmptyState title={tr('ไม่พบลูกค้า', 'No customers')} />
        ) : (
          <table className="table-base">
            <thead>
              <tr>
                <th>ID</th>
                <th>{tr('ชื่อ', 'Name')}</th>
                <th>{tr('ประเภท', 'Type')}</th>
                <th>{tr('รหัส', 'Code')}</th>
                <th>ERPNext</th>
                <th className="text-right">Tickets</th>
                <th>{tr('สร้างเมื่อ', 'Created')}</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((c) => (
                <tr key={c.id}>
                  <td className="text-xs text-slate-500">{c.id}</td>
                  <td className="font-medium">
                    {c.name} {!c.is_active && <Badge color="slate">{tr('ปิด', 'inactive')}</Badge>}
                  </td>
                  <td className="text-xs">{label(CUSTOMER_TYPE_LABELS, c.customer_type, lang)}</td>
                  <td className="text-xs">{c.code ?? '-'}</td>
                  <td className="text-xs">{c.erpnext_customer ?? '-'}</td>
                  <td className="text-right">{c.ticket_count}</td>
                  <td className="text-xs whitespace-nowrap">{formatDateTime(c.created_at, lang)}</td>
                  <td className="space-x-1 text-right whitespace-nowrap">
                    <button type="button" className="btn-secondary px-2.5 py-1 text-xs" onClick={() => setContactsFor(c)}>
                      {tr('ผู้ติดต่อ', 'Contacts')}
                    </button>
                    <button type="button" className="btn-secondary px-2.5 py-1 text-xs" onClick={() => setEditing(c)}>
                      {tr('แก้ไข', 'Edit')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data && data.total > 0 && <Pagination page={page} pageSize={50} total={data.total} onPage={setPage} />}
      </div>
      {editing && (
        <CustomerDialog
          customer={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
      {contactsFor && <ContactsDialog customer={contactsFor} onClose={() => setContactsFor(null)} />}
    </div>
  )
}

function CustomerDialog({ customer, onClose, onSaved }: { customer: Customer; onClose: () => void; onSaved: () => void }) {
  const { tr, lang } = useI18n()
  const toast = useToast()
  const [f, setF] = useState({
    name: customer.name,
    code: customer.code ?? '',
    customer_type: customer.customer_type,
    tax_id: customer.tax_id ?? '',
    address: customer.address ?? '',
    notes: customer.notes ?? '',
    is_active: customer.is_active,
  })
  const [erp, setErp] = useState(customer.erpnext_customer ?? '')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  async function save() {
    setBusy(true)
    setErr(null)
    try {
      await api.patch(`/admin/customers/${customer.id}`, f)
      if ((erp || null) !== customer.erpnext_customer) {
        await api.post('/admin/integrations/mappings', {
          local_entity_type: 'customer',
          local_id: String(customer.id),
          external_doctype: 'Customer',
          external_name: erp.trim() || null,
        })
      }
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
      title={tr('แก้ไขข้อมูลลูกค้า', 'Edit customer')}
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
        <label className="block">
          <span className="label">{tr('ชื่อหน่วยงาน', 'Organisation name')}</span>
          <input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="label">{tr('ประเภท', 'Type')}</span>
            <select className="input" value={f.customer_type} onChange={(e) => setF({ ...f, customer_type: e.target.value })}>
              {Object.keys(CUSTOMER_TYPE_LABELS).map((c) => (
                <option key={c} value={c}>
                  {label(CUSTOMER_TYPE_LABELS, c, lang)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">{tr('รหัสลูกค้า', 'Customer code')}</span>
            <input className="input" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} />
          </label>
          <label className="block">
            <span className="label">{tr('เลขประจำตัวผู้เสียภาษี', 'Tax ID')}</span>
            <input className="input" value={f.tax_id} onChange={(e) => setF({ ...f, tax_id: e.target.value })} />
          </label>
          <label className="block">
            <span className="label">ERPNext Customer</span>
            <input className="input" placeholder="CUST-00001" value={erp} onChange={(e) => setErp(e.target.value)} />
          </label>
        </div>
        <label className="block">
          <span className="label">{tr('ที่อยู่', 'Address')}</span>
          <textarea className="input" rows={2} value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} />
        </label>
        <label className="block">
          <span className="label">{tr('หมายเหตุ', 'Notes')}</span>
          <textarea className="input" rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />
        </label>
        <Toggle checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} label={tr('ใช้งาน', 'Active')} />
        {err && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{err}</p>}
      </div>
    </Modal>
  )
}

function ContactsDialog({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const { tr, lang } = useI18n()
  const { data, error } = useApi<Contact[]>(`/admin/customers/${customer.id}/contacts`)
  return (
    <Modal open wide title={`${tr('ผู้ติดต่อ', 'Contacts')} — ${customer.name}`} onClose={onClose}>
      {error && <ErrorBox message={error.message} />}
      {!data ? (
        <Loading />
      ) : data.length === 0 ? (
        <EmptyState title={tr('ไม่มีผู้ติดต่อ', 'No contacts')} />
      ) : (
        <div className="overflow-x-auto">
          <table className="table-base">
            <thead>
              <tr>
                <th>{tr('ชื่อ', 'Name')}</th>
                <th>{tr('แผนก', 'Department')}</th>
                <th>{tr('โทรศัพท์', 'Phone')}</th>
                <th>{tr('อีเมล', 'Email')}</th>
                <th>LINE</th>
                <th>{tr('สร้างเมื่อ', 'Created')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((c) => (
                <tr key={c.id}>
                  <td>
                    {c.name} {c.anonymized_at && <Badge color="slate">{tr('ลบข้อมูลแล้ว', 'anonymised')}</Badge>}
                  </td>
                  <td className="text-xs">{c.department ?? '-'}</td>
                  <td className="text-xs">{c.phone ?? '-'}</td>
                  <td className="text-xs">{c.email ?? '-'}</td>
                  <td className="text-xs">{c.line_verified ? '✓' : '-'}</td>
                  <td className="text-xs">{formatDateTime(c.created_at, lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}
