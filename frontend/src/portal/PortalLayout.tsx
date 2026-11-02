import { Link, Outlet } from 'react-router-dom'
import { LanguageToggle } from '../components/LanguageToggle'
import { useI18n } from '../i18n'

export function Logo({ compact }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white/10 ring-1 ring-white/25">
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden>
          <path d="M10 4h4v6h6v4h-6v6h-4v-6H4v-4h6z" fill="#fff" />
        </svg>
      </span>
      {!compact && (
        <span className="leading-tight">
          <span className="block text-[15px] font-bold tracking-wide text-white">BUC</span>
          <span className="block text-[11px] font-medium text-brand-200">Customer Service Center</span>
        </span>
      )}
    </span>
  )
}

export function PortalLayout() {
  const { tr } = useI18n()
  return (
    <div className="flex min-h-dvh flex-col bg-slate-100">
      <header className="sticky top-0 z-30 bg-navy-900 text-white shadow-md">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3">
          <Link to="/" className="rounded-md" aria-label="BUC Customer Service Center">
            <Logo />
          </Link>
          <div className="flex items-center gap-2">
            <Link to="/track" className="hidden rounded-full px-3 py-1.5 text-sm font-medium text-brand-100 hover:bg-white/10 sm:inline-block">
              {tr('ติดตามสถานะ', 'Track request')}
            </Link>
            <LanguageToggle dark />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 pt-5 pb-10">
        <Outlet />
      </main>
      <footer className="safe-bottom border-t border-slate-200 bg-white px-4 pt-4 text-center text-xs text-slate-500">
        <p>© {new Date().getFullYear()} {tr('บริษัท บางกอกยูนิเทรด จำกัด', 'The Bangkok Unitrade Co., Ltd.')}</p>
        <p className="mt-1 space-x-3">
          <Link to="/privacy" className="underline hover:text-brand-700">
            {tr('ประกาศความเป็นส่วนตัว', 'Privacy notice')}
          </Link>
          <Link to="/track" className="underline hover:text-brand-700">
            {tr('ติดตามสถานะคำขอ', 'Track a request')}
          </Link>
        </p>
      </footer>
    </div>
  )
}
