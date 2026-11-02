import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { IconSearch } from '../components/Icons'
import { FieldError } from '../components/ui'
import { useI18n } from '../i18n'

const LINK_RE = /\/track\/(BUC-[A-Z]{3}-\d{4}-\d{5,})\/?#t=([A-Za-z0-9_-]{10,128})/i

/** Manual tracking: ticket number + token, or paste the whole tracking link. */
export function TrackPage() {
  const { tr } = useI18n()
  const navigate = useNavigate()
  const [link, setLink] = useState('')
  const [number, setNumber] = useState('')
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)

  function go(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const m = link.trim().match(LINK_RE)
    if (link.trim()) {
      if (!m) {
        setError(tr('ลิงก์ไม่ถูกต้อง กรุณาวางลิงก์ติดตามสถานะที่ได้รับ', 'Invalid link. Please paste the tracking link you received.'))
        return
      }
      navigate(`/track/${m[1].toUpperCase()}#t=${m[2]}`)
      return
    }
    const num = number.trim().toUpperCase()
    if (!/^BUC-[A-Z]{3}-\d{4}-\d{5,}$/.test(num) || token.trim().length < 10) {
      setError(tr('กรุณากรอกเลขที่ Ticket และรหัสติดตามให้ถูกต้อง', 'Please enter a valid ticket number and tracking code'))
      return
    }
    navigate(`/track/${num}#t=${encodeURIComponent(token.trim())}`)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-navy-900">{tr('ติดตามสถานะคำขอ', 'Track your request')}</h1>
      <form onSubmit={go} className="card space-y-4 p-4 sm:p-6" noValidate>
        <div>
          <label htmlFor="track-link" className="label">
            {tr('วางลิงก์ติดตามสถานะ', 'Paste your tracking link')}
          </label>
          <input
            id="track-link"
            className="input"
            value={link}
            onChange={(e) => setLink(e.target.value)}
            placeholder="https://.../track/BUC-SRV-2026-00001#t=..."
            inputMode="url"
            autoComplete="off"
          />
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span className="h-px flex-1 bg-slate-200" />
          {tr('หรือ', 'or')}
          <span className="h-px flex-1 bg-slate-200" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="track-number" className="label">
              {tr('เลขที่ Ticket', 'Ticket number')}
            </label>
            <input
              id="track-number"
              className="input uppercase"
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              placeholder="BUC-SRV-2026-00001"
              autoComplete="off"
            />
          </div>
          <div>
            <label htmlFor="track-token" className="label">
              {tr('รหัสติดตาม (ส่วนท้ายของลิงก์หลัง #t=)', 'Tracking code (after #t= in the link)')}
            </label>
            <input id="track-token" className="input" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" />
          </div>
        </div>
        <FieldError message={error} />
        <button type="submit" className="btn-primary min-h-12 w-full">
          <IconSearch size={18} /> {tr('ตรวจสอบสถานะ', 'Check status')}
        </button>
        <p className="text-xs text-slate-500">
          {tr(
            'เพื่อความปลอดภัย ระบบต้องใช้ทั้งเลขที่ Ticket และรหัสติดตาม หากทำลิงก์หาย กรุณาติดต่อเจ้าหน้าที่เพื่อขอลิงก์ใหม่',
            'For your security both the ticket number and the tracking code are required. If you lost the link, contact us for a new one.',
          )}
        </p>
      </form>
    </div>
  )
}
