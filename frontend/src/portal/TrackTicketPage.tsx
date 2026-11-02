import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { FileRules, PublicTicketView } from '../api/types'
import { FileUploader } from '../components/FileUploader'
import { IconClock } from '../components/Icons'
import { Badge, ErrorBox, Loading, Spinner, cx } from '../components/ui'
import { useI18n } from '../i18n'
import { formatDateTime } from '../lib/dates'
import { revokeItems, type UploadItem } from '../lib/files'

const CATEGORY_COLOR: Record<string, string> = {
  NEW: 'blue',
  OPEN: 'amber',
  WAITING: 'orange',
  RESOLVED: 'green',
  CLOSED: 'slate',
  CANCELLED: 'red',
}

function tokenFromHash(hash: string): string {
  const m = hash.match(/[#&]t=([^&]+)/)
  return m ? decodeURIComponent(m[1]) : ''
}

export function TrackTicketPage() {
  const { ticketNumber = '' } = useParams()
  const location = useLocation()
  const { tr, lang } = useI18n()
  const token = tokenFromHash(location.hash)
  const [view, setView] = useState<PublicTicketView | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    if (!token) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    api
      .post<PublicTicketView>('/public/track', { ticket_number: ticketNumber.toUpperCase(), token })
      .then(setView)
      .catch((e: ApiError) => setError(e))
      .finally(() => setLoading(false))
  }, [ticketNumber, token])

  // A different ticket number / token must never keep showing the previous ticket.
  useEffect(() => {
    setView(null)
  }, [ticketNumber, token])
  useEffect(load, [load])

  if (!token) {
    return (
      <div className="space-y-3">
        <ErrorBox message={tr('ลิงก์ไม่สมบูรณ์ — ไม่พบรหัสติดตาม กรุณาใช้ลิงก์ที่ได้รับหลังส่งคำขอ', 'Incomplete link — tracking code missing.')} />
        <Link to="/track" className="btn-secondary">
          {tr('กรอกข้อมูลติดตามสถานะ', 'Enter tracking details')}
        </Link>
      </div>
    )
  }
  if (loading && !view) return <Loading />
  if (error && !view) {
    return (
      <div className="space-y-3">
        <ErrorBox message={error.message} onRetry={error.status === 404 ? undefined : load} />
        <Link to="/track" className="btn-secondary">
          {tr('ลองอีกครั้ง', 'Try again')}
        </Link>
      </div>
    )
  }
  if (!view) return null

  return (
    <div className="space-y-4">
      <section className="card p-4 sm:p-6">
        <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{tr('เลขที่ Ticket', 'Ticket number')}</p>
        <h1 className="text-xl font-bold break-all text-navy-900 sm:text-2xl">{view.ticket_number}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge color={CATEGORY_COLOR[view.status_category] ?? 'gray'} className="px-3 py-1 text-sm">
            <span data-testid="tracking-status">{lang === 'en' ? view.status_name_en : view.status_name_th}</span>
          </Badge>
          <span className="text-sm text-slate-500">{lang === 'en' ? view.request_type_name_en : view.request_type_name_th}</span>
        </div>
        <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-slate-500">{tr('เรื่อง', 'Subject')}</dt>
            <dd className="font-medium break-words text-slate-800">{view.subject}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{tr('วันที่ส่งคำขอ', 'Submitted')}</dt>
            <dd className="text-slate-800">{formatDateTime(view.created_at, lang)}</dd>
          </div>
        </dl>
      </section>

      <section className="card p-4 sm:p-6">
        <h2 className="font-semibold text-navy-900">{tr('ความคืบหน้า', 'Progress')}</h2>
        <ol className="mt-4 space-y-0">
          {view.timeline.map((e, i) => (
            <li key={i} className="relative flex gap-3 pb-5 last:pb-0">
              {i < view.timeline.length - 1 && <span className="absolute top-6 left-[11px] h-full w-px bg-slate-200" aria-hidden />}
              <span
                className={cx(
                  'relative z-10 mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full ring-4 ring-white',
                  e.type === 'STATUS' ? 'bg-brand-600 text-white' : e.author === 'CUSTOMER' ? 'bg-slate-400 text-white' : 'bg-emerald-600 text-white',
                )}
              >
                <span className="h-2 w-2 rounded-full bg-white" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1 text-xs text-slate-500">
                  <IconClock size={12} /> {formatDateTime(e.at, lang)}
                </p>
                {e.type === 'STATUS' ? (
                  <p className="text-sm font-medium text-slate-800">
                    {tr('สถานะ', 'Status')}: {lang === 'en' ? e.status_name_en : e.status_name_th}
                  </p>
                ) : (
                  <div
                    className={cx(
                      'mt-1 rounded-lg p-3 text-sm whitespace-pre-line',
                      e.author === 'CUSTOMER' ? 'bg-slate-100 text-slate-700' : 'bg-emerald-50 text-emerald-900',
                    )}
                  >
                    <p className="mb-1 text-xs font-semibold">
                      {e.author === 'CUSTOMER' ? tr('ท่าน', 'You') : tr('เจ้าหน้าที่ BUC', 'BUC staff')}
                    </p>
                    {e.body}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      </section>

      {view.can_reply && (
        <ReplyBox ticketNumber={view.ticket_number} token={token} rules={view.reply_file_rules} waiting={view.status === 'WAITING_CUSTOMER'} onSent={setView} />
      )}

      <Link to="/" className="btn-secondary min-h-11 w-full">
        {tr('กลับหน้าหลัก', 'Back to home')}
      </Link>
    </div>
  )
}

function ReplyBox({
  ticketNumber,
  token,
  rules,
  waiting,
  onSent,
}: {
  ticketNumber: string
  token: string
  /** Server-computed: remaining customer upload quota for this ticket and allowed types. */
  rules: FileRules
  waiting: boolean
  onSent: (v: PublicTicketView) => void
}) {
  const { tr } = useI18n()
  const [message, setMessage] = useState('')
  const [items, setItems] = useState<UploadItem[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState(false)

  const itemsRef = useRef(items)
  itemsRef.current = items
  useEffect(() => () => revokeItems(itemsRef.current), [])

  async function send(e: FormEvent) {
    e.preventDefault()
    if (!message.trim()) {
      setError(tr('กรุณากรอกข้อความ', 'Please enter a message'))
      return
    }
    setBusy(true)
    setError(null)
    const fd = new FormData()
    fd.append('payload', JSON.stringify({ ticket_number: ticketNumber, token, message: message.trim() }))
    for (const it of items) fd.append('files', it.file, it.file.name)
    try {
      const v = await api.upload<PublicTicketView>('/public/track/reply', fd)
      setMessage('')
      revokeItems(items)
      setItems([])
      setOk(true)
      onSent(v)
    } catch (err) {
      setError((err as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={send} className={cx('card space-y-3 p-4 sm:p-6', waiting && 'ring-2 ring-orange-300')}>
      <h2 className="font-semibold text-navy-900">
        {waiting ? tr('เจ้าหน้าที่ขอข้อมูลเพิ่มเติม', 'We need more information') : tr('ส่งข้อมูลเพิ่มเติม', 'Send more information')}
      </h2>
      <div>
        <label htmlFor="reply-message" className="label">
          {tr('ข้อความ', 'Message')}
        </label>
        <textarea id="reply-message" className="input" rows={4} maxLength={5000} value={message} onChange={(e) => setMessage(e.target.value)} />
      </div>
      {rules.max_files > 0 && (
        <FileUploader label={tr('ไฟล์แนบเพิ่มเติม (ถ้ามี)', 'Additional files (optional)')} rules={rules} items={items} onChange={setItems} compact />
      )}
      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
      {ok && <p className="text-sm text-emerald-700">{tr('ส่งข้อมูลเรียบร้อยแล้ว', 'Sent successfully')}</p>}
      <button type="submit" className="btn-primary min-h-12 w-full" disabled={busy}>
        {busy && <Spinner className="h-4 w-4" />} {tr('ส่งข้อมูล', 'Send')}
      </button>
    </form>
  )
}
