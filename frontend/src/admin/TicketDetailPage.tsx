import { useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { TicketDetail, TokenResult, TransitionOption } from '../api/types'
import { IconChevronLeft, IconDownload, IconFile, IconUpload } from '../components/Icons'
import { useToast } from '../components/Toast'
import {
  ConfirmDialog,
  CopyButton,
  ErrorBox,
  KeyValue,
  Loading,
  Modal,
  PriorityBadge,
  SampleBadge,
  SectionCard,
  Spinner,
  StatusBadge,
  cx,
} from '../components/ui'
import { CUSTOMER_TYPE_LABELS, PRIORITY_LABELS, label, useI18n } from '../i18n'
import { formatDateTime, fromBangkokLocalInput, toBangkokLocalInput } from '../lib/dates'
import { formatBytes } from '../lib/files'
import { PageHeader } from './AdminLayout'
import { useAuth, useLookups } from './auth'
import { ImageViewer } from './ImageViewer'
import { useApi } from './useApi'

const ACTION_LABEL: Record<string, { th: string; en: string }> = {
  WAITING_CUSTOMER: { th: 'ขอข้อมูลเพิ่มเติมจากลูกค้า', en: 'Request customer information' },
  RESOLVED: { th: 'ดำเนินการเสร็จสิ้น (Resolve)', en: 'Resolve ticket' },
  CLOSED: { th: 'ปิดงาน', en: 'Close ticket' },
  CANCELLED: { th: 'ยกเลิก Ticket', en: 'Cancel ticket' },
}

export function TicketDetailPage() {
  const { id = '' } = useParams()
  const { tr, pick, lang } = useI18n()
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const { data: t, setData, error, loading, reload } = useApi<TicketDetail>(`/tickets/${id}`)
  const [transition, setTransition] = useState<TransitionOption | null>(null)
  const [assignMode, setAssignMode] = useState<'assign' | 'transfer' | null>(null)
  const [viewer, setViewer] = useState<number | null>(null)
  const [confirmToken, setConfirmToken] = useState(false)
  const [token, setToken] = useState<TokenResult | null>(null)
  const [busy, setBusy] = useState(false)

  const images = useMemo(() => (t?.attachments ?? []).filter((a) => a.kind === 'IMAGE'), [t])
  const docs = useMemo(() => (t?.attachments ?? []).filter((a) => a.kind !== 'IMAGE'), [t])

  if (error) {
    return (
      <div className="space-y-3">
        <ErrorBox message={error.status === 404 ? tr('ไม่พบ Ticket หรือท่านไม่มีสิทธิ์เข้าถึง', 'Ticket not found or not accessible') : error.message} onRetry={reload} />
        <Link to="/admin/tickets" className="btn-secondary">
          {tr('กลับไปรายการ', 'Back to list')}
        </Link>
      </div>
    )
  }
  if (!t) return loading ? <Loading /> : null

  async function selfAssign() {
    if (!t || !user) return
    setBusy(true)
    try {
      const r = await api.post<TicketDetail>(`/tickets/${t.id}/assign`, { assigned_user_id: user.id, reason: 'รับงานเอง' })
      setData(r)
      toast.success(tr('รับงานเรียบร้อย', 'Ticket taken'))
    } catch (e) {
      toast.error((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  async function regenerate() {
    if (!t) return
    setBusy(true)
    try {
      setToken(await api.post<TokenResult>(`/tickets/${t.id}/tracking-token`))
      setConfirmToken(false)
    } catch (e) {
      toast.error((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  const p = t.permissions

  return (
    <div className="space-y-5">
      <Link to="/admin/tickets" className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
        <IconChevronLeft size={16} /> {tr('รายการ Ticket', 'Tickets')}
      </Link>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-2">
            <span data-testid="detail-ticket-number">{t.ticket_number}</span>
            <StatusBadge status={t.status} />
            <PriorityBadge priority={t.priority} />
            {t.is_overdue && <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">{tr('เกินกำหนด', 'Overdue')}</span>}
            {t.is_sample && <SampleBadge />}
          </span>
        }
        subtitle={t.subject}
      />
      {t.anonymized_at && (
        <p className="rounded-lg bg-slate-200 p-3 text-sm text-slate-700">
          {tr('ข้อมูลส่วนบุคคลของ Ticket นี้ถูกลบตามนโยบายการเก็บรักษาข้อมูลแล้ว', 'Personal data of this ticket was removed under the retention policy.')}
        </p>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          {/* A. Ticket information */}
          <SectionCard title={tr('A. ข้อมูล Ticket', 'A. Ticket information')}>
            <dl className="divide-y divide-slate-100">
              <KeyValue label={tr('ประเภทคำขอ', 'Request type')}>{pick(t.request_type, 'name')}</KeyValue>
              <KeyValue label={tr('เรื่อง', 'Subject')}>{t.subject}</KeyValue>
              <KeyValue label={tr('ความสำคัญ', 'Priority')}>
                <PriorityBadge priority={t.priority} />
              </KeyValue>
              <KeyValue label={tr('สถานะ', 'Status')}>
                <StatusBadge status={t.status} />
              </KeyValue>
              <KeyValue label={tr('ช่องทาง', 'Source')}>{t.source}</KeyValue>
              <KeyValue label={tr('วันที่สร้าง', 'Created')}>{formatDateTime(t.created_at, lang)}</KeyValue>
            </dl>
            <div className="mt-3">
              <p className="text-sm text-slate-500">{tr('รายละเอียด', 'Description')}</p>
              <p className="mt-1 rounded-lg bg-slate-50 p-3 text-sm whitespace-pre-line text-slate-800">{t.description}</p>
            </div>
            {t.details.length > 0 && (
              <div className="mt-4">
                <p className="mb-1 text-sm font-semibold text-slate-700">{tr('ข้อมูลเพิ่มเติมจากแบบฟอร์ม', 'Form details')}</p>
                <dl className="grid gap-x-6 sm:grid-cols-2">
                  {t.details.map((d) => (
                    <KeyValue key={d.key} label={pick(d, 'label')}>
                      <span className="whitespace-pre-line">{d.value}</span>
                    </KeyValue>
                  ))}
                </dl>
              </div>
            )}
          </SectionCard>

          {/* F. Attachments */}
          <SectionCard
            title={`${tr('F. ไฟล์แนบ', 'F. Attachments')} (${t.attachments.length})`}
            actions={p.can_upload && <UploadButton ticketId={t.id} onUploaded={setData} />}
          >
            {t.attachments.length === 0 ? (
              <p className="text-sm text-slate-500">{tr('ไม่มีไฟล์แนบ', 'No attachments')}</p>
            ) : (
              <>
                {images.length > 0 && (
                  <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6" data-testid="attachment-gallery">
                    {images.map((a, i) => (
                      <li key={a.id}>
                        <button
                          type="button"
                          onClick={() => setViewer(i)}
                          className="group relative block w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-100"
                          aria-label={tr(`เปิดรูป ${a.original_filename}`, `Open ${a.original_filename}`)}
                        >
                          <img src={a.url} alt={a.original_filename} loading="lazy" className="aspect-square w-full object-cover transition group-hover:scale-105" />
                          <span
                            className={cx(
                              'absolute top-1 left-1 rounded px-1.5 py-0.5 text-[10px] font-medium',
                              a.source === 'CUSTOMER' ? 'bg-brand-600 text-white' : 'bg-slate-700 text-white',
                            )}
                          >
                            {a.source === 'CUSTOMER' ? tr('ลูกค้า', 'Customer') : tr('เจ้าหน้าที่', 'Staff')}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {docs.length > 0 && (
                  <ul className="mt-3 divide-y divide-slate-100 rounded-lg border border-slate-200">
                    {docs.map((a) => (
                      <li key={a.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                        <IconFile className="text-red-600" />
                        <span className="min-w-0 flex-1 truncate">{a.original_filename}</span>
                        <span className="text-xs text-slate-500">{formatBytes(a.size_bytes)}</span>
                        <a href={`${a.url}?download=1`} className="btn-ghost px-2 py-1" aria-label={tr('ดาวน์โหลด', 'Download')}>
                          <IconDownload size={16} />
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </SectionCard>

          {/* D + E. Timeline & comments */}
          <SectionCard title={tr('D. ประวัติและความคิดเห็น', 'D. Timeline & comments')}>
            <Timeline ticket={t} />
            {p.can_comment && <CommentBox ticketId={t.id} onSaved={setData} />}
          </SectionCard>
        </div>

        <div className="space-y-5">
          {/* G. Actions */}
          <SectionCard title={tr('G. การดำเนินการ', 'G. Actions')}>
            <div className="space-y-2">
              {p.can_self_assign && (
                <button type="button" className="btn-primary w-full" onClick={selfAssign} disabled={busy}>
                  {tr('รับงานนี้', 'Take this ticket')}
                </button>
              )}
              {p.can_assign && (
                <button type="button" className="btn-secondary w-full" onClick={() => setAssignMode('assign')}>
                  {tr('มอบหมายงาน / ความสำคัญ / กำหนดเสร็จ', 'Assign / priority / due date')}
                </button>
              )}
              {p.can_transfer && (
                <button type="button" className="btn-secondary w-full" onClick={() => setAssignMode('transfer')}>
                  {tr('โอนไปแผนกอื่น', 'Transfer department')}
                </button>
              )}
              {t.allowed_transitions.length > 0 && (
                <div className="pt-2">
                  <p className="mb-1.5 text-xs font-semibold text-slate-500">{tr('เปลี่ยนสถานะ', 'Change status')}</p>
                  <div className="flex flex-col gap-1.5">
                    {t.allowed_transitions.map((tr_) => (
                      <button
                        key={tr_.to_status}
                        type="button"
                        className={cx(
                          'btn w-full justify-start border text-left',
                          tr_.to_status === 'RESOLVED'
                            ? 'border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                            : tr_.to_status === 'CANCELLED'
                              ? 'border-red-200 bg-white text-red-700 hover:bg-red-50'
                              : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
                        )}
                        onClick={() => setTransition(tr_)}
                        data-testid={`transition-${tr_.to_status}`}
                      >
                        → {ACTION_LABEL[tr_.to_status] ? ACTION_LABEL[tr_.to_status][lang] : pick(tr_, 'name')}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {!p.can_change_status && (
                <p className="text-xs text-slate-500">{tr('ท่านไม่มีสิทธิ์เปลี่ยนสถานะ Ticket นี้', 'You cannot change the status of this ticket')}</p>
              )}
              {p.can_regenerate_token && !t.anonymized_at && (
                <button type="button" className="btn-ghost w-full text-xs" onClick={() => setConfirmToken(true)}>
                  {tr('ออกลิงก์ติดตามสถานะใหม่ให้ลูกค้า', 'Issue a new customer tracking link')}
                </button>
              )}
            </div>
          </SectionCard>

          {/* B. Customer */}
          <SectionCard title={tr('B. ข้อมูลลูกค้า', 'B. Customer')}>
            <dl className="divide-y divide-slate-100">
              <KeyValue label={tr('โรงพยาบาล / หน่วยงาน', 'Organization')}>{t.customer.name}</KeyValue>
              <KeyValue label={tr('ประเภท', 'Type')}>{label(CUSTOMER_TYPE_LABELS, t.customer.customer_type, lang)}</KeyValue>
              <KeyValue label={tr('ผู้ติดต่อ', 'Contact')}>{t.contact.name}</KeyValue>
              <KeyValue label={tr('แผนก', 'Department')}>{t.contact.department || '-'}</KeyValue>
              <KeyValue label={tr('โทรศัพท์', 'Telephone')}>
                {t.contact.phone ? (
                  <a className="text-brand-700 hover:underline" href={`tel:${t.contact.phone}`}>
                    {t.contact.phone}
                  </a>
                ) : (
                  '-'
                )}
              </KeyValue>
              <KeyValue label={tr('อีเมล', 'Email')}>
                {t.contact.email ? (
                  <a className="break-all text-brand-700 hover:underline" href={`mailto:${t.contact.email}`}>
                    {t.contact.email}
                  </a>
                ) : (
                  '-'
                )}
              </KeyValue>
              <KeyValue label={tr('ความยินยอม PDPA', 'PDPA consent')}>
                {t.privacy_consent_version ? `v${t.privacy_consent_version} · ${formatDateTime(t.privacy_consent_at, lang)}` : '-'}
              </KeyValue>
            </dl>
          </SectionCard>

          {/* C. Assignment */}
          <SectionCard title={tr('C. การมอบหมายงาน', 'C. Assignment')}>
            <dl className="divide-y divide-slate-100">
              <KeyValue label={tr('แผนกรับผิดชอบ', 'Department')}>{pick(t.department, 'name')}</KeyValue>
              <KeyValue label={tr('ผู้รับผิดชอบ', 'Assigned staff')}>{t.assigned_user?.full_name ?? tr('ยังไม่มอบหมาย', 'Unassigned')}</KeyValue>
              <KeyValue label={tr('กำหนดเสร็จ', 'Due date')}>
                <span className={cx(t.is_overdue && 'font-semibold text-red-700')}>{formatDateTime(t.due_at, lang)}</span>
              </KeyValue>
              <KeyValue label={tr('ตอบกลับครั้งแรก', 'First response')}>{formatDateTime(t.first_response_at, lang)}</KeyValue>
              <KeyValue label={tr('เสร็จสิ้น', 'Resolved')}>{formatDateTime(t.resolved_at, lang)}</KeyValue>
              <KeyValue label={tr('ปิดงาน', 'Closed')}>{formatDateTime(t.closed_at, lang)}</KeyValue>
            </dl>
          </SectionCard>
        </div>
      </div>

      {viewer !== null && <ImageViewer images={images} index={viewer} onClose={() => setViewer(null)} onIndex={setViewer} />}

      <StatusDialog
        ticket={t}
        transition={transition}
        onClose={() => setTransition(null)}
        onSaved={(d) => {
          setData(d)
          setTransition(null)
          toast.success(tr('เปลี่ยนสถานะเรียบร้อย', 'Status updated'))
        }}
      />
      <AssignDialog
        ticket={t}
        mode={assignMode}
        onClose={() => setAssignMode(null)}
        onSaved={(d) => {
          setAssignMode(null)
          if ('code' in d && d.code === 'TRANSFERRED_OUT') {
            toast.info(tr('โอนงานแล้ว Ticket นี้ไม่อยู่ในขอบเขตสิทธิ์ของท่านแล้ว', 'Transferred — the ticket is no longer in your scope'))
            navigate('/admin/tickets')
            return
          }
          setData(d as TicketDetail)
          toast.success(tr('บันทึกการมอบหมายงานแล้ว', 'Assignment saved'))
        }}
      />
      <ConfirmDialog
        open={confirmToken}
        title={tr('ออกลิงก์ติดตามสถานะใหม่', 'Issue a new tracking link')}
        message={tr(
          'ลิงก์ติดตามสถานะเดิมของลูกค้าจะใช้งานไม่ได้ทันที และระบบจะแสดงลิงก์ใหม่เพียงครั้งเดียว ต้องการดำเนินการต่อหรือไม่?',
          'The customer’s existing tracking link will stop working immediately and the new link is shown only once. Continue?',
        )}
        busy={busy}
        onCancel={() => setConfirmToken(false)}
        onConfirm={regenerate}
      />
      <Modal open={!!token} title={tr('ลิงก์ติดตามสถานะใหม่', 'New tracking link')} onClose={() => setToken(null)}>
        {token && (
          <div className="space-y-3 text-sm">
            <p className="rounded-lg bg-amber-50 p-3 text-amber-900">
              {tr('ส่งลิงก์นี้ให้ลูกค้าผ่านช่องทางที่ปลอดภัย ระบบจะไม่แสดงลิงก์นี้อีก', 'Send this link to the customer through a trusted channel. It will not be shown again.')}
            </p>
            <p className="rounded-lg border bg-slate-50 p-3 font-mono text-xs break-all">{token.tracking_url}</p>
            <CopyButton text={token.tracking_url} label={tr('คัดลอกลิงก์', 'Copy link')} />
          </div>
        )}
      </Modal>
    </div>
  )
}

function UploadButton({ ticketId, onUploaded }: { ticketId: number; onUploaded: (d: TicketDetail) => void }) {
  const { tr } = useI18n()
  const toast = useToast()
  const ref = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  async function upload(files: FileList | null) {
    if (!files?.length) return
    const fd = new FormData()
    for (const f of Array.from(files).slice(0, 10)) fd.append('files', f, f.name)
    setBusy(true)
    try {
      onUploaded(await api.upload<TicketDetail>(`/tickets/${ticketId}/attachments`, fd))
      toast.success(tr('อัปโหลดไฟล์แล้ว', 'Files uploaded'))
    } catch (e) {
      toast.error((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={() => ref.current?.click()} disabled={busy}>
        {busy ? <Spinner className="h-4 w-4" /> : <IconUpload size={16} />} {tr('อัปโหลด', 'Upload')}
      </button>
      <input
        ref={ref}
        type="file"
        multiple
        accept="image/jpeg,image/png,application/pdf"
        className="hidden"
        onChange={(e) => {
          void upload(e.target.files)
          e.target.value = ''
        }}
      />
    </>
  )
}

type TimelineEntry = { at: string; key: string; node: ReactNode; first?: boolean }

function Timeline({ ticket: t }: { ticket: TicketDetail }) {
  const { tr, pick, lang } = useI18n()
  const { lookups } = useLookups()
  const statusName = (code: string | null) => {
    if (!code) return '-'
    const s = lookups?.statuses.find((x) => x.code === code)
    return s ? pick(s, 'name') : code
  }
  const entries: TimelineEntry[] = []
  for (const h of t.history) {
    entries.push({
      at: h.created_at,
      key: `h${h.id}`,
      first: h.from_status === null,
      node: (
        <div>
          <p className="text-sm text-slate-800">
            <span className="font-medium">{h.actor_name ?? (h.actor_type === 'CUSTOMER' ? tr('ลูกค้า', 'Customer') : tr('ระบบ', 'System'))}</span>{' '}
            {h.from_status ? (
              <>
                {tr('เปลี่ยนสถานะ', 'changed status')} {statusName(h.from_status)} → <b>{statusName(h.to_status)}</b>
              </>
            ) : (
              <>
                {tr('สร้าง Ticket', 'created the ticket')} (<b>{statusName(h.to_status)}</b>)
              </>
            )}
          </p>
          {h.comment && <p className="mt-0.5 text-xs text-slate-500">{tr('หมายเหตุภายใน', 'Internal note')}: {h.comment}</p>}
        </div>
      ),
    })
  }
  for (const a of t.assignments) {
    const kind =
      a.assignment_type === 'TRANSFER'
        ? tr('โอนงาน', 'transferred')
        : a.assignment_type === 'INITIAL' || a.assignment_type === 'AUTO'
          ? tr('กำหนดแผนกเริ่มต้น', 'initial routing')
          : a.assignment_type === 'SELF'
            ? tr('รับงานเอง', 'took the ticket')
            : tr('มอบหมายงาน', 'assigned')
    entries.push({
      at: a.created_at,
      key: `a${a.id}`,
      node: (
        <div className="text-sm text-slate-700">
          <span className="font-medium">{a.assigned_by ?? tr('ระบบ', 'System')}</span> {kind}:{' '}
          {a.from_department && a.from_department !== a.to_department && <>{a.from_department} → </>}
          <b>{a.to_department}</b>
          {a.to_user && (
            <>
              {' '}
              · {tr('ผู้รับผิดชอบ', 'assignee')} <b>{a.to_user}</b>
            </>
          )}
          {a.priority && <> · {PRIORITY_LABELS[a.priority]?.[lang] ?? a.priority}</>}
          {a.due_at && (
            <>
              {' '}
              · {tr('กำหนดเสร็จ', 'due')} {formatDateTime(a.due_at, lang)}
            </>
          )}
          {a.reason && <p className="text-xs text-slate-500">{a.reason}</p>}
        </div>
      ),
    })
  }
  for (const c of t.comments) {
    const internal = c.visibility === 'INTERNAL'
    entries.push({
      at: c.created_at,
      key: `c${c.id}`,
      node: (
        <div
          className={cx(
            'rounded-lg border p-3 text-sm',
            internal ? 'border-amber-200 bg-amber-50' : c.author_type === 'CUSTOMER' ? 'border-slate-200 bg-slate-50' : 'border-emerald-200 bg-emerald-50',
          )}
        >
          <p className="mb-1 flex flex-wrap items-center gap-2 text-xs font-semibold">
            <span>{c.author_type === 'CUSTOMER' ? tr('ลูกค้า', 'Customer') : (c.author_name ?? tr('ระบบ', 'System'))}</span>
            {internal ? (
              <span className="rounded bg-amber-200 px-1.5 py-0.5 text-amber-900">🔒 {tr('บันทึกภายใน (ลูกค้าไม่เห็น)', 'Internal note (hidden from customer)')}</span>
            ) : (
              <span className="rounded bg-emerald-200 px-1.5 py-0.5 text-emerald-900">
                {c.author_type === 'CUSTOMER' ? tr('ข้อความจากลูกค้า', 'From customer') : tr('ลูกค้าเห็นข้อความนี้', 'Visible to customer')}
              </span>
            )}
          </p>
          <p className="whitespace-pre-line text-slate-800">{c.body}</p>
        </div>
      ),
    })
  }
  // The creation entry always comes first; the rest is chronological.
  entries.sort((a, b) => Number(!!b.first) - Number(!!a.first) || a.at.localeCompare(b.at))
  return (
    <ol className="space-y-4" data-testid="timeline">
      {entries.map((e) => (
        <li key={e.key} className="grid grid-cols-[110px_minmax(0,1fr)] gap-3 sm:grid-cols-[140px_minmax(0,1fr)]">
          <time className="pt-0.5 text-xs text-slate-500">{formatDateTime(e.at, lang)}</time>
          {e.node}
        </li>
      ))}
    </ol>
  )
}

function CommentBox({ ticketId, onSaved }: { ticketId: number; onSaved: (d: TicketDetail) => void }) {
  const { tr } = useI18n()
  const toast = useToast()
  const [body, setBody] = useState('')
  const [visibility, setVisibility] = useState<'INTERNAL' | 'PUBLIC'>('INTERNAL')
  const [busy, setBusy] = useState(false)
  async function save() {
    if (!body.trim()) return
    setBusy(true)
    try {
      onSaved(await api.post<TicketDetail>(`/tickets/${ticketId}/comments`, { body: body.trim(), visibility }))
      setBody('')
      toast.success(tr('บันทึกความคิดเห็นแล้ว', 'Comment added'))
    } catch (e) {
      toast.error((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="mt-5 border-t border-slate-100 pt-4">
      <p className="label">{tr('E. เพิ่มความคิดเห็น', 'E. Add comment')}</p>
      <div className="mb-2 inline-flex rounded-lg bg-slate-100 p-1 text-sm" role="radiogroup">
        {(['INTERNAL', 'PUBLIC'] as const).map((v) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={visibility === v}
            onClick={() => setVisibility(v)}
            className={cx(
              'rounded-md px-3 py-1.5 font-medium',
              visibility === v ? (v === 'INTERNAL' ? 'bg-amber-500 text-white' : 'bg-emerald-600 text-white') : 'text-slate-600',
            )}
          >
            {v === 'INTERNAL' ? `🔒 ${tr('บันทึกภายใน', 'Internal note')}` : tr('อัปเดตถึงลูกค้า', 'Customer-visible update')}
          </button>
        ))}
      </div>
      <textarea
        className={cx('input', visibility === 'PUBLIC' && 'border-emerald-300')}
        rows={3}
        maxLength={5000}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder={
          visibility === 'INTERNAL'
            ? tr('ข้อความนี้จะไม่แสดงให้ลูกค้าเห็น', 'Not visible to the customer')
            : tr('ลูกค้าจะเห็นข้อความนี้ในหน้าติดตามสถานะ (และทางอีเมลหากมี)', 'The customer will see this on the tracking page (and by e-mail)')
        }
      />
      <div className="mt-2 flex justify-end">
        <button type="button" className="btn-primary" onClick={save} disabled={busy || !body.trim()}>
          {busy && <Spinner className="h-4 w-4" />} {tr('บันทึก', 'Save')}
        </button>
      </div>
    </div>
  )
}

function StatusDialog({
  ticket,
  transition,
  onClose,
  onSaved,
}: {
  ticket: TicketDetail
  transition: TransitionOption | null
  onClose: () => void
  onSaved: (d: TicketDetail) => void
}) {
  const { tr, pick, lang } = useI18n()
  const [comment, setComment] = useState('')
  const [publicMsg, setPublicMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<ApiError | null>(null)
  const open = !!transition
  const needsPublic = transition?.to_status === 'WAITING_CUSTOMER'
  const needsComment = !!transition?.requires_comment

  async function save() {
    if (!transition) return
    setBusy(true)
    setErr(null)
    try {
      const d = await api.post<TicketDetail>(`/tickets/${ticket.id}/status`, {
        to_status: transition.to_status,
        comment: comment.trim() || null,
        public_message: publicMsg.trim() || null,
      })
      setComment('')
      setPublicMsg('')
      onSaved(d)
    } catch (e) {
      setErr(e as ApiError)
    } finally {
      setBusy(false)
    }
  }
  const title = transition ? (ACTION_LABEL[transition.to_status]?.[lang] ?? `${tr('เปลี่ยนสถานะเป็น', 'Change status to')} ${pick(transition, 'name')}`) : ''
  const disabled = busy || (needsPublic && !publicMsg.trim()) || (needsComment && !comment.trim() && !publicMsg.trim())
  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            {tr('ยกเลิก', 'Cancel')}
          </button>
          <button type="button" className={transition?.to_status === 'CANCELLED' ? 'btn-danger' : 'btn-primary'} onClick={save} disabled={disabled} data-testid="confirm-status">
            {busy && <Spinner className="h-4 w-4" />} {tr('ยืนยัน', 'Confirm')}
          </button>
        </>
      }
    >
      <div className="space-y-3 text-sm">
        <p className="text-slate-600">
          {statusLine(ticket, transition, pick)}
        </p>
        <label className="block">
          <span className="label">
            {needsPublic ? tr('ข้อมูลที่ต้องการจากลูกค้า (ลูกค้าเห็นข้อความนี้)', 'Information needed from the customer (visible to customer)') : tr('ข้อความถึงลูกค้า (ไม่บังคับ — ลูกค้าเห็น)', 'Message to customer (optional — visible)')}
            {needsPublic && <span className="text-red-600"> *</span>}
          </span>
          <textarea className="input border-emerald-300" rows={3} maxLength={5000} value={publicMsg} onChange={(e) => setPublicMsg(e.target.value)} />
        </label>
        <label className="block">
          <span className="label">
            {tr('เหตุผล / หมายเหตุภายใน', 'Reason / internal note')}
            {needsComment ? <span className="text-red-600"> *</span> : <span className="text-xs text-slate-400"> ({tr('ไม่บังคับ', 'optional')})</span>}
          </span>
          <textarea className="input" rows={2} maxLength={5000} value={comment} onChange={(e) => setComment(e.target.value)} />
        </label>
        {err && <p className="rounded bg-red-50 p-2 text-red-700">{err.message}</p>}
      </div>
    </Modal>
  )
}

function statusLine(t: TicketDetail, transition: TransitionOption | null, pick: (o: object, b: string) => string) {
  if (!transition) return null
  return (
    <>
      {pick(t.status, 'name')} → <b>{pick(transition, 'name')}</b>
    </>
  )
}

function AssignDialog({
  ticket,
  mode,
  onClose,
  onSaved,
}: {
  ticket: TicketDetail
  mode: 'assign' | 'transfer' | null
  onClose: () => void
  onSaved: (d: TicketDetail | { code: string }) => void
}) {
  const { tr, pick, lang } = useI18n()
  const { lookups } = useLookups()
  const [dept, setDept] = useState('')
  const [userId, setUserId] = useState('')
  const [priority, setPriority] = useState('')
  const [due, setDue] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [initFor, setInitFor] = useState<string | null>(null)

  const key = mode ? `${mode}-${ticket.id}-${ticket.updated_at}` : null
  if (key && key !== initFor) {
    setInitFor(key)
    setDept(String(ticket.department.id))
    setUserId(mode === 'assign' && ticket.assigned_user ? String(ticket.assigned_user.id) : '')
    setPriority(ticket.priority)
    setDue(toBangkokLocalInput(ticket.due_at))
    setReason('')
    setErr(null)
  }

  const deptId = Number(dept)
  const users = (lookups?.users ?? []).filter((u) => u.role === 'ADMIN' || u.department_ids.includes(deptId))

  async function save() {
    setBusy(true)
    setErr(null)
    try {
      const body: Record<string, unknown> = { reason: reason.trim() || null }
      if (deptId && deptId !== ticket.department.id) body.department_id = deptId
      if (mode === 'assign') {
        if (userId) body.assigned_user_id = Number(userId)
        else if (ticket.assigned_user) body.unassign = true
        if (priority !== ticket.priority) body.priority = priority
        const dueIso = fromBangkokLocalInput(due)
        if (dueIso && toBangkokLocalInput(dueIso) !== toBangkokLocalInput(ticket.due_at)) body.due_at = dueIso
      } else if (userId) {
        body.assigned_user_id = Number(userId)
      }
      onSaved(await api.post<TicketDetail | { code: string }>(`/tickets/${ticket.id}/assign`, body))
    } catch (e) {
      setErr((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={!!mode}
      title={mode === 'transfer' ? tr('โอนไปแผนกอื่น', 'Transfer to another department') : tr('มอบหมายงาน', 'Assign ticket')}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            {tr('ยกเลิก', 'Cancel')}
          </button>
          <button type="button" className="btn-primary" onClick={save} disabled={busy || (mode === 'transfer' && deptId === ticket.department.id)}>
            {busy && <Spinner className="h-4 w-4" />} {tr('บันทึก', 'Save')}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <label className="block">
          <span className="label">{tr('แผนกรับผิดชอบ', 'Responsible department')}</span>
          <select
            className="input"
            value={dept}
            onChange={(e) => {
              setDept(e.target.value)
              setUserId('')
            }}
          >
            {lookups?.departments.filter((d) => d.is_active || d.id === ticket.department.id).map((d) => (
              <option key={d.id} value={d.id}>
                {pick(d, 'name')}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="label">{tr('ผู้รับผิดชอบ', 'Assigned staff')}</span>
          <select className="input" value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">{tr('— ยังไม่มอบหมาย —', '— Unassigned —')}</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </select>
        </label>
        {mode === 'assign' && (
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="label">{tr('ความสำคัญ', 'Priority')}</span>
              <select className="input" value={priority} onChange={(e) => setPriority(e.target.value)}>
                {Object.keys(PRIORITY_LABELS).map((p) => (
                  <option key={p} value={p}>
                    {PRIORITY_LABELS[p][lang]}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">{tr('กำหนดเสร็จ (เวลาไทย)', 'Due date (Bangkok)')}</span>
              <input type="datetime-local" className="input" value={due} onChange={(e) => setDue(e.target.value)} />
            </label>
          </div>
        )}
        <label className="block">
          <span className="label">{tr('เหตุผล', 'Reason')}</span>
          <input className="input" value={reason} maxLength={2000} onChange={(e) => setReason(e.target.value)} />
        </label>
        {err && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{err}</p>}
      </div>
    </Modal>
  )
}
