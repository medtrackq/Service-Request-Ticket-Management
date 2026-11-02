import { useState } from 'react'
import { ApiError, api } from '../../api/client'
import type { Role } from '../../api/types'
import { useToast } from '../../components/Toast'
import { Badge, ConfirmDialog, CopyButton, ErrorBox, FieldError, Loading, Modal, Spinner, Toggle, cx } from '../../components/ui'
import { ROLE_LABELS, label, useI18n } from '../../i18n'
import { formatDateTime } from '../../lib/dates'
import { PageHeader } from '../AdminLayout'
import { useAuth, useLookups } from '../auth'
import { useApi } from '../useApi'

interface AdminUser {
  id: number
  username: string
  full_name: string
  email: string | null
  phone: string | null
  role: Role
  is_active: boolean
  must_change_password: boolean
  locked_until: string | null
  last_login_at: string | null
  departments: { id: number; name_th: string; name_en: string }[]
  department_ids: number[]
}

export function UsersPage() {
  const { tr, pick, lang } = useI18n()
  const { user: me } = useAuth()
  const { reload: reloadLookups } = useLookups()
  const toast = useToast()
  const [q, setQ] = useState('')
  const { data, error, loading, reload } = useApi<AdminUser[]>('/admin/users')
  const [editing, setEditing] = useState<AdminUser | 'new' | null>(null)
  const [resetFor, setResetFor] = useState<AdminUser | null>(null)
  const [secret, setSecret] = useState<{ username: string; password: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const rows = (data ?? []).filter((u) => !q || `${u.full_name} ${u.username} ${u.email ?? ''}`.toLowerCase().includes(q.toLowerCase()))

  async function doReset() {
    if (!resetFor) return
    setBusy(true)
    try {
      const r = await api.post<{ temporary_password: string }>(`/admin/users/${resetFor.id}/reset-password`)
      setSecret({ username: resetFor.username, password: r.temporary_password })
      setResetFor(null)
      reload()
    } catch (e) {
      toast.error((e as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={tr('ผู้ใช้งาน', 'Users')}
        subtitle={tr('จัดการบัญชีเจ้าหน้าที่ บทบาท และแผนก', 'Manage staff accounts, roles and departments')}
        actions={
          <button type="button" className="btn-primary" onClick={() => setEditing('new')}>
            + {tr('เพิ่มผู้ใช้', 'Add user')}
          </button>
        }
      />
      <input className="input max-w-sm" placeholder={tr('ค้นหาชื่อ / username / อีเมล', 'Search name / username / email')} value={q} onChange={(e) => setQ(e.target.value)} />
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      <div className="card overflow-x-auto">
        {!data && loading ? (
          <Loading />
        ) : (
          <table className="table-base">
            <thead>
              <tr>
                <th>{tr('ชื่อ', 'Name')}</th>
                <th>{tr('บทบาท', 'Role')}</th>
                <th>{tr('แผนก', 'Departments')}</th>
                <th>{tr('สถานะ', 'Status')}</th>
                <th>{tr('เข้าระบบล่าสุด', 'Last login')}</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((u) => (
                <tr key={u.id} className={cx(!u.is_active && 'opacity-60')}>
                  <td>
                    <p className="font-medium text-slate-800">{u.full_name}</p>
                    <p className="text-xs text-slate-500">
                      {u.username}
                      {u.email && ` · ${u.email}`}
                    </p>
                  </td>
                  <td className="whitespace-nowrap">{label(ROLE_LABELS, u.role, lang)}</td>
                  <td className="text-xs">{u.departments.map((d) => pick(d, 'name')).join(', ') || '-'}</td>
                  <td className="space-x-1 whitespace-nowrap">
                    <Badge color={u.is_active ? 'green' : 'slate'}>{u.is_active ? tr('ใช้งาน', 'Active') : tr('ปิดใช้งาน', 'Inactive')}</Badge>
                    {u.must_change_password && <Badge color="yellow">{tr('ต้องเปลี่ยนรหัส', 'Must change password')}</Badge>}
                    {u.locked_until && new Date(u.locked_until) > new Date() && <Badge color="red">{tr('ถูกล็อก', 'Locked')}</Badge>}
                  </td>
                  <td className="whitespace-nowrap text-xs">{formatDateTime(u.last_login_at, lang)}</td>
                  <td className="space-x-1 text-right whitespace-nowrap">
                    <button type="button" className="btn-secondary px-2.5 py-1 text-xs" onClick={() => setEditing(u)}>
                      {tr('แก้ไข', 'Edit')}
                    </button>
                    {u.id !== me?.id && (
                      <button type="button" className="btn-secondary px-2.5 py-1 text-xs" onClick={() => setResetFor(u)}>
                        {tr('รีเซ็ตรหัสผ่าน', 'Reset password')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editing && (
        <UserDialog
          user={editing === 'new' ? null : editing}
          isSelf={editing !== 'new' && editing.id === me?.id}
          onClose={() => setEditing(null)}
          onSaved={(r) => {
            setEditing(null)
            reload()
            reloadLookups()
            if (r?.temporary_password) setSecret({ username: r.username, password: r.temporary_password })
            else toast.success(tr('บันทึกแล้ว', 'Saved'))
          }}
        />
      )}
      <ConfirmDialog
        open={!!resetFor}
        title={tr('รีเซ็ตรหัสผ่าน', 'Reset password')}
        message={tr(
          `ระบบจะสร้างรหัสผ่านชั่วคราวให้ ${resetFor?.full_name ?? ''} และออกจากระบบทุกอุปกรณ์ ผู้ใช้ต้องเปลี่ยนรหัสผ่านเมื่อเข้าสู่ระบบครั้งถัดไป`,
          `A temporary password will be generated for ${resetFor?.full_name ?? ''} and all sessions signed out.`,
        )}
        busy={busy}
        onCancel={() => setResetFor(null)}
        onConfirm={doReset}
      />
      <Modal open={!!secret} title={tr('รหัสผ่านชั่วคราว', 'Temporary password')} onClose={() => setSecret(null)}>
        {secret && (
          <div className="space-y-3 text-sm">
            <p className="rounded-lg bg-amber-50 p-3 text-amber-900">
              {tr('แสดงเพียงครั้งเดียว กรุณาส่งให้ผู้ใช้ผ่านช่องทางที่ปลอดภัย', 'Shown only once. Hand it to the user through a secure channel.')}
            </p>
            <p>
              {tr('ชื่อผู้ใช้', 'Username')}: <b>{secret.username}</b>
            </p>
            <p className="rounded-lg border bg-slate-50 p-3 font-mono text-base">{secret.password}</p>
            <CopyButton text={secret.password} />
          </div>
        )}
      </Modal>
    </div>
  )
}

function UserDialog({
  user,
  isSelf,
  onClose,
  onSaved,
}: {
  user: AdminUser | null
  isSelf: boolean
  onClose: () => void
  onSaved: (r: { username: string; temporary_password?: string | null } | null) => void
}) {
  const { tr, pick, lang } = useI18n()
  const { lookups } = useLookups()
  const [form, setForm] = useState({
    username: user?.username ?? '',
    full_name: user?.full_name ?? '',
    email: user?.email ?? '',
    phone: user?.phone ?? '',
    role: (user?.role ?? 'STAFF') as Role,
    department_ids: user?.department_ids ?? ([] as number[]),
    is_active: user?.is_active ?? true,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }))

  async function save() {
    setBusy(true)
    setErrors({})
    const body = { ...form, email: form.email || null, phone: form.phone || null }
    try {
      if (user) {
        const { username: _ignored, ...rest } = body
        void _ignored
        await api.patch(`/admin/users/${user.id}`, rest)
        onSaved(null)
      } else {
        const r = await api.post<{ username: string; temporary_password: string | null }>('/admin/users', body)
        onSaved(r)
      }
    } catch (e) {
      const ae = e as ApiError
      setErrors({ ...ae.fields, form: ae.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      title={user ? tr('แก้ไขผู้ใช้', 'Edit user') : tr('เพิ่มผู้ใช้', 'Add user')}
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
        {!user && (
          <label className="block">
            <span className="label">Username</span>
            <input className="input" value={form.username} onChange={(e) => set('username', e.target.value)} autoComplete="off" />
            <FieldError message={errors.username} />
          </label>
        )}
        <label className="block">
          <span className="label">{tr('ชื่อ-นามสกุล', 'Full name')}</span>
          <input className="input" value={form.full_name} onChange={(e) => set('full_name', e.target.value)} />
          <FieldError message={errors.full_name} />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="label">{tr('อีเมล', 'Email')}</span>
            <input className="input" type="email" value={form.email} onChange={(e) => set('email', e.target.value)} />
            <FieldError message={errors.email} />
          </label>
          <label className="block">
            <span className="label">{tr('โทรศัพท์', 'Phone')}</span>
            <input className="input" value={form.phone} onChange={(e) => set('phone', e.target.value)} />
          </label>
        </div>
        <label className="block">
          <span className="label">{tr('บทบาท', 'Role')}</span>
          <select className="input" value={form.role} disabled={isSelf} onChange={(e) => set('role', e.target.value as Role)}>
            {(['ADMIN', 'MANAGER', 'STAFF'] as const).map((r) => (
              <option key={r} value={r}>
                {label(ROLE_LABELS, r, lang)}
              </option>
            ))}
          </select>
        </label>
        <fieldset>
          <legend className="label">{tr('แผนก', 'Departments')}</legend>
          <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {lookups?.departments.map((d) => (
              <label key={d.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.department_ids.includes(d.id)}
                  onChange={(e) =>
                    set('department_ids', e.target.checked ? [...form.department_ids, d.id] : form.department_ids.filter((x) => x !== d.id))
                  }
                />
                {pick(d, 'name')}
              </label>
            ))}
          </div>
        </fieldset>
        {!isSelf && <Toggle checked={form.is_active} onChange={(v) => set('is_active', v)} label={tr('เปิดใช้งานบัญชี', 'Account active')} />}
        {!user && (
          <p className="text-xs text-slate-500">
            {tr('ระบบจะสร้างรหัสผ่านชั่วคราวและแสดงหลังบันทึก ผู้ใช้ต้องเปลี่ยนรหัสผ่านเมื่อเข้าสู่ระบบครั้งแรก', 'A temporary password is generated and shown once; the user must change it at first login.')}
          </p>
        )}
        {errors.form && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{errors.form}</p>}
      </div>
    </Modal>
  )
}
