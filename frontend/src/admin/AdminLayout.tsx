import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  IconBuilding,
  IconChart,
  IconDashboard,
  IconLink,
  IconLogout,
  IconMenu,
  IconSettings,
  IconShield,
  IconTicket,
  IconUsers,
  IconX,
  IconBell,
  IconDocument,
} from '../components/Icons'
import { LanguageToggle } from '../components/LanguageToggle'
import { cx } from '../components/ui'
import { ROLE_LABELS, label, useI18n } from '../i18n'
import { Logo } from '../portal/PortalLayout'
import { useAuth } from './auth'
import { NotificationBell } from './NotificationBell'

interface NavItem {
  to: string
  th: string
  en: string
  icon: ReactNode
  end?: boolean
}

export function AdminLayout() {
  const { tr, lang } = useI18n()
  const { user, permissions, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => setOpen(false), [location.pathname])

  const main: NavItem[] = [
    { to: '/admin', th: 'แดชบอร์ด', en: 'Dashboard', icon: <IconDashboard size={18} />, end: true },
    { to: '/admin/tickets', th: 'รายการ Ticket', en: 'Tickets', icon: <IconTicket size={18} /> },
    ...(permissions?.can_view_reports ? [{ to: '/admin/reports', th: 'รายงาน', en: 'Reports', icon: <IconChart size={18} /> }] : []),
    { to: '/admin/notifications', th: 'การแจ้งเตือน', en: 'Notifications', icon: <IconBell size={18} /> },
  ]
  const admin: NavItem[] = [
    { to: '/admin/users', th: 'ผู้ใช้งาน', en: 'Users', icon: <IconUsers size={18} /> },
    { to: '/admin/departments', th: 'แผนก', en: 'Departments', icon: <IconBuilding size={18} /> },
    { to: '/admin/request-types', th: 'ประเภทคำขอ & ฟอร์ม', en: 'Request types & forms', icon: <IconDocument size={18} /> },
    { to: '/admin/workflow', th: 'Workflow สถานะ', en: 'Workflow', icon: <IconTicket size={18} /> },
    { to: '/admin/assignment-rules', th: 'กฎการมอบหมายงาน', en: 'Assignment rules', icon: <IconUsers size={18} /> },
    { to: '/admin/customers', th: 'ลูกค้า', en: 'Customers', icon: <IconBuilding size={18} /> },
    { to: '/admin/settings', th: 'ตั้งค่าระบบ', en: 'Settings', icon: <IconSettings size={18} /> },
    { to: '/admin/integrations', th: 'การเชื่อมต่อ (LINE/ERPNext)', en: 'Integrations', icon: <IconLink size={18} /> },
    { to: '/admin/notification-logs', th: 'บันทึกการส่งแจ้งเตือน', en: 'Notification logs', icon: <IconBell size={18} /> },
    { to: '/admin/audit-logs', th: 'Audit Log', en: 'Audit log', icon: <IconShield size={18} /> },
  ]

  const link = (n: NavItem) => (
    <NavLink
      key={n.to}
      to={n.to}
      end={n.end}
      className={({ isActive }) =>
        cx(
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition',
          isActive ? 'bg-white/12 font-semibold text-white' : 'text-brand-100/85 hover:bg-white/8 hover:text-white',
        )
      }
    >
      {n.icon}
      <span>{lang === 'en' ? n.en : n.th}</span>
    </NavLink>
  )

  const sidebar = (
    <nav className="flex h-full flex-col gap-1 overflow-y-auto px-3 pb-4" aria-label="Admin">
      <div className="px-2 pt-4 pb-5">
        <Logo />
      </div>
      {main.map(link)}
      {user?.role === 'ADMIN' && (
        <>
          <p className="mt-5 mb-1 px-3 text-[11px] font-semibold tracking-wider text-brand-200/70 uppercase">
            {tr('ผู้ดูแลระบบ', 'Administration')}
          </p>
          {admin.map(link)}
        </>
      )}
    </nav>
  )

  return (
    <div className="min-h-dvh bg-slate-100">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 bg-navy-900 lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-navy-950/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-navy-900 shadow-xl">
            <button
              type="button"
              className="absolute top-3 right-3 rounded-md p-1.5 text-white/80 hover:bg-white/10"
              onClick={() => setOpen(false)}
              aria-label="close menu"
            >
              <IconX />
            </button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur">
          <button type="button" className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100 lg:hidden" onClick={() => setOpen(true)} aria-label="menu">
            <IconMenu />
          </button>
          <div className="flex-1" />
          <LanguageToggle />
          <NotificationBell />
          <div className="hidden text-right sm:block">
            <p className="text-sm leading-tight font-semibold text-navy-900">{user?.full_name}</p>
            <p className="text-xs text-slate-500">{label(ROLE_LABELS, user?.role, lang)}</p>
          </div>
          <div className="flex items-center">
            <button type="button" className="btn-ghost px-2" onClick={() => navigate('/admin/change-password')} title={tr('เปลี่ยนรหัสผ่าน', 'Change password')}>
              <IconSettings size={18} />
            </button>
            <button
              type="button"
              className="btn-ghost px-2"
              title={tr('ออกจากระบบ', 'Sign out')}
              onClick={async () => {
                await logout()
                navigate('/admin/login', { replace: true })
              }}
            >
              <IconLogout size={18} />
            </button>
          </div>
        </header>
        <main className="mx-auto max-w-[1400px] p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-xl font-bold text-navy-900 sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
