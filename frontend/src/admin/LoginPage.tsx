import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import type { ApiError } from '../api/client'
import { LanguageToggle } from '../components/LanguageToggle'
import { Spinner } from '../components/ui'
import { useI18n } from '../i18n'
import { Logo } from '../portal/PortalLayout'
import { useAuth } from './auth'

export function LoginPage() {
  const { tr } = useI18n()
  const { login, status, user } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const next = params.get('next')
  const safeNext = next && next.startsWith('/admin') && !next.startsWith('//') ? next : '/admin'

  if (status === 'authenticated' && user) {
    return <Navigate to={user.must_change_password ? '/admin/change-password' : safeNext} replace />
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const p = await login(username.trim(), password)
      navigate(p.user.must_change_password ? '/admin/change-password' : safeNext, { replace: true })
    } catch (err) {
      setError((err as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-gradient-to-br from-navy-950 via-navy-900 to-brand-700 px-4 py-10">
      <div className="mb-6 flex w-full max-w-sm items-center justify-between">
        <Logo />
        <LanguageToggle dark />
      </div>
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl" noValidate>
        <h1 className="text-xl font-bold text-navy-900">{tr('เข้าสู่ระบบเจ้าหน้าที่', 'Staff sign in')}</h1>
        <p className="mt-1 text-sm text-slate-500">{tr('ระบบจัดการ Ticket บริการลูกค้า', 'Customer service ticket management')}</p>
        <div className="mt-5 space-y-4">
          <div>
            <label htmlFor="username" className="label">
              {tr('ชื่อผู้ใช้หรืออีเมล', 'Username or email')}
            </label>
            <input id="username" className="input" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>
          <div>
            <label htmlFor="password" className="label">
              {tr('รหัสผ่าน', 'Password')}
            </label>
            <input
              id="password"
              type="password"
              className="input"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && (
            <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
              {error}
            </p>
          )}
          <button type="submit" className="btn-primary min-h-11 w-full" disabled={busy || !username || !password}>
            {busy && <Spinner className="h-4 w-4" />} {tr('เข้าสู่ระบบ', 'Sign in')}
          </button>
        </div>
      </form>
      <p className="mt-6 text-xs text-brand-100/70">© The Bangkok Unitrade Co., Ltd.</p>
    </div>
  )
}
