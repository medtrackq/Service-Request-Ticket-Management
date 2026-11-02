import { Link, useLocation } from 'react-router-dom'
import type { SubmissionResult } from '../api/types'
import { IconCheck, IconLink } from '../components/Icons'
import { CopyButton, EmptyState } from '../components/ui'
import { useI18n } from '../i18n'
import { formatDateTime } from '../lib/dates'
import { LAST_SUBMISSION_KEY } from './RequestFormPage'

function readStored(): SubmissionResult | null {
  try {
    const raw = sessionStorage.getItem(LAST_SUBMISSION_KEY)
    return raw ? (JSON.parse(raw) as SubmissionResult) : null
  } catch {
    return null
  }
}

/** Turn the absolute tracking URL from the API into an in-app path (keeps the #t= fragment). */
export function trackingPath(url: string): string {
  try {
    const u = new URL(url, window.location.origin)
    return u.pathname + u.hash
  } catch {
    return url
  }
}

export function SuccessPage() {
  const { tr, lang } = useI18n()
  const location = useLocation()
  const result = (location.state as { result?: SubmissionResult } | null)?.result ?? readStored()

  if (!result) {
    return (
      <div className="card">
        <EmptyState title={tr('ไม่พบข้อมูลการส่งคำขอล่าสุด', 'No recent submission found')}>
          <Link to="/" className="btn-primary mt-3">
            {tr('กลับหน้าหลัก', 'Back to home')}
          </Link>
        </EmptyState>
      </div>
    )
  }
  const name = lang === 'en' ? result.request_type_name_en : result.request_type_name_th
  const localUrl = result.tracking_url ? `${window.location.origin}${trackingPath(result.tracking_url)}` : null

  return (
    <div className="space-y-4">
      <section className="card overflow-hidden text-center">
        <div className="bg-emerald-600 px-4 py-6 text-white">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-white/20">
            <IconCheck size={32} />
          </span>
          <h1 className="mt-3 text-xl font-bold">{tr('ส่งคำขอเรียบร้อยแล้ว', 'Request submitted')}</h1>
          <p className="mt-1 text-sm text-emerald-50">
            {tr('เจ้าหน้าที่จะตรวจสอบและติดต่อกลับโดยเร็ว', 'Our team will review it and get back to you soon')}
          </p>
        </div>
        <div className="space-y-3 px-4 py-5">
          <p className="text-sm text-slate-500">{tr('เลขที่ Ticket ของท่าน', 'Your ticket number')}</p>
          <p className="text-2xl font-bold tracking-wide break-all text-navy-900 sm:text-3xl" data-testid="ticket-number">
            {result.ticket_number}
          </p>
          <CopyButton text={result.ticket_number} label={tr('คัดลอกเลขที่ Ticket', 'Copy ticket number')} />
          <dl className="mx-auto mt-2 max-w-sm space-y-1 text-left text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">{tr('ประเภท', 'Type')}</dt>
              <dd className="text-right font-medium">{name}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">{tr('เรื่อง', 'Subject')}</dt>
              <dd className="text-right font-medium break-words">{result.subject}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">{tr('วันที่ส่ง', 'Submitted')}</dt>
              <dd className="text-right">{formatDateTime(result.created_at, lang)}</dd>
            </div>
            {result.attachments > 0 && (
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">{tr('ไฟล์แนบ', 'Attachments')}</dt>
                <dd className="text-right">{result.attachments}</dd>
              </div>
            )}
          </dl>
        </div>
      </section>

      {localUrl ? (
        <section className="card space-y-3 p-4">
          <h2 className="flex items-center gap-2 font-semibold text-navy-900">
            <IconLink size={18} className="text-brand-600" /> {tr('ลิงก์ติดตามสถานะ', 'Tracking link')}
          </h2>
          <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
            {tr(
              'กรุณาบันทึกลิงก์นี้ไว้ (เช่น คัดลอกเก็บไว้ หรือแคปหน้าจอ) ลิงก์นี้ใช้ดูสถานะคำขอของท่าน และไม่ควรเผยแพร่ให้ผู้อื่น',
              'Please save this link (copy it or take a screenshot). It lets you check the status of your request — do not share it with others.',
            )}
          </p>
          <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs break-all text-slate-700" data-testid="tracking-url">
            {localUrl}
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <CopyButton text={localUrl} label={tr('คัดลอกลิงก์', 'Copy link')} className="min-h-11 flex-1" />
            <Link to={trackingPath(result.tracking_url!)} className="btn-primary min-h-11 flex-1" data-testid="open-tracking">
              {tr('ดูสถานะตอนนี้', 'View status now')}
            </Link>
          </div>
        </section>
      ) : (
        <section className="card p-4 text-sm text-slate-600">
          {result.replayed
            ? tr(
                'คำขอนี้ถูกส่งไปแล้วก่อนหน้านี้ และลิงก์ติดตามสถานะได้แสดงไว้ในครั้งแรก หากไม่ได้บันทึกไว้ กรุณาติดต่อเจ้าหน้าที่พร้อมแจ้งเลขที่ Ticket',
                'This request was already submitted and its tracking link was shown the first time. If you did not save it, please contact us with your ticket number.',
              )
            : tr('กรุณาติดต่อเจ้าหน้าที่พร้อมแจ้งเลขที่ Ticket เพื่อสอบถามสถานะ', 'Please contact us with your ticket number for status updates.')}
        </section>
      )}

      <Link to="/" className="btn-secondary min-h-11 w-full">
        {tr('กลับหน้าหลัก', 'Back to home')}
      </Link>
    </div>
  )
}
