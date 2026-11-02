import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import { FieldError, Spinner } from '../components/ui'
import { useToast } from '../components/Toast'
import { useI18n } from '../i18n'
import { useAuth } from './auth'

export function ChangePasswordPage() {
  const { tr } = useI18n()
  const { user, refresh, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const forced = !!user?.must_change_password

  async function submit(e: FormEvent) {
    e.preventDefault()
    const errs: Record<string, string> = {}
    if (next.length < 10) errs.new_password = tr('รหัสผ่านต้องมีอย่างน้อย 10 ตัวอักษร', 'At least 10 characters')
    if (next !== confirm) errs.confirm = tr('รหัสผ่านไม่ตรงกัน', 'Passwords do not match')
    setErrors(errs)
    if (Object.keys(errs).length) return
    setBusy(true)
    try {
      await api.post('/auth/change-password', { current_password: current, new_password: next })
      toast.success(tr('เปลี่ยนรหัสผ่านเรียบร้อยแล้ว', 'Password changed'))
      await refresh()
      navigate('/admin', { replace: true })
    } catch (err) {
      const ae = err as ApiError
      setErrors({ ...ae.fields, form: ae.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <form onSubmit={submit} className="card space-y-4 p-6" noValidate>
        <h1 className="text-xl font-bold text-navy-900">{tr('เปลี่ยนรหัสผ่าน', 'Change password')}</h1>
        {forced && (
          <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
            {tr('กรุณาตั้งรหัสผ่านใหม่ก่อนเริ่มใช้งานระบบ', 'Please set a new password before using the system.')}
          </p>
        )}
        <div>
          <label className="label" htmlFor="cur">
            {tr('รหัสผ่านปัจจุบัน', 'Current password')}
          </label>
          <input id="cur" type="password" className="input" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          <FieldError message={errors.current_password} />
        </div>
        <div>
          <label className="label" htmlFor="new">
            {tr('รหัสผ่านใหม่', 'New password')}
          </label>
          <input id="new" type="password" className="input" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
          <p className="mt-1 text-xs text-slate-500">
            {tr('อย่างน้อย 10 ตัวอักษร มีทั้งตัวอักษรและตัวเลข/สัญลักษณ์', 'At least 10 characters, mixing letters and digits/symbols')}
          </p>
          <FieldError message={errors.new_password} />
        </div>
        <div>
          <label className="label" htmlFor="confirm">
            {tr('ยืนยันรหัสผ่านใหม่', 'Confirm new password')}
          </label>
          <input id="confirm" type="password" className="input" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          <FieldError message={errors.confirm} />
        </div>
        {errors.form && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{errors.form}</p>}
        <div className="flex gap-2">
          <button type="submit" className="btn-primary flex-1" disabled={busy}>
            {busy && <Spinner className="h-4 w-4" />} {tr('บันทึก', 'Save')}
          </button>
          {forced ? (
            <button type="button" className="btn-secondary" onClick={() => logout().then(() => navigate('/admin/login'))}>
              {tr('ออกจากระบบ', 'Sign out')}
            </button>
          ) : (
            <button type="button" className="btn-secondary" onClick={() => navigate(-1)}>
              {tr('ยกเลิก', 'Cancel')}
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
