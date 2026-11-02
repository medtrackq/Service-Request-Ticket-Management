import { Link } from 'react-router-dom'
import { IconChevronRight, IconMail, IconPhone, IconSearch, RequestTypeIcon } from '../components/Icons'
import { ErrorBox, Loading } from '../components/ui'
import { useI18n } from '../i18n'
import { usePortalConfig } from './usePortal'

const ACCENTS = [
  'bg-brand-50 text-brand-700',
  'bg-sky-50 text-sky-700',
  'bg-indigo-50 text-indigo-700',
  'bg-cyan-50 text-cyan-700',
  'bg-blue-50 text-blue-700',
  'bg-slate-100 text-navy-800',
]

export function HomePage() {
  const { tr, pick, lang } = useI18n()
  const { data, error, reload } = usePortalConfig()

  if (error) return <ErrorBox message={error} onRetry={reload} />
  if (!data) return <Loading />
  const s = data.settings

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-2xl bg-gradient-to-br from-navy-900 via-navy-800 to-brand-700 px-5 py-6 text-white shadow-lg">
        <p className="text-xs font-semibold tracking-[0.18em] text-brand-200 uppercase">Bangkok Unitrade</p>
        <h1 className="mt-1 text-2xl leading-tight font-bold sm:text-3xl">BUC Customer Service Center</h1>
        <p className="mt-2 text-sm leading-relaxed text-brand-100 sm:text-base">
          {lang === 'en' ? s['portal.welcome_en'] : s['portal.welcome_th']}
        </p>
        <p className="mt-3 text-xs text-brand-200">{tr('กรุณาเลือกบริการที่ต้องการ', 'Please choose a service below')}</p>
      </section>

      <section aria-label={tr('บริการ', 'Services')}>
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {data.request_types.map((rt, i) => (
            <li key={rt.code}>
              <Link
                to={`/request/${rt.slug}`}
                className="group flex min-h-[84px] items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-300 hover:shadow-md active:scale-[0.99]"
              >
                <span className={`grid h-12 w-12 shrink-0 place-items-center rounded-xl ${ACCENTS[i % ACCENTS.length]}`}>
                  <RequestTypeIcon icon={rt.icon} size={26} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-base font-semibold text-navy-900">{pick(rt, 'name')}</span>
                  <span className="mt-0.5 block text-sm leading-snug text-slate-500">{pick(rt, 'description')}</span>
                </span>
                <IconChevronRight className="shrink-0 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-brand-600" />
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <Link
        to="/track"
        className="flex items-center gap-4 rounded-xl border border-brand-200 bg-brand-50 p-4 text-navy-900 transition hover:bg-brand-100"
      >
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-white text-brand-700 shadow-sm">
          <IconSearch />
        </span>
        <span className="flex-1">
          <span className="block font-semibold">{tr('ติดตามสถานะคำขอ', 'Track your request')}</span>
          <span className="block text-sm text-slate-600">
            {tr('ใช้ลิงก์ติดตามสถานะที่ได้รับหลังส่งคำขอ', 'Use the tracking link you received after submitting')}
          </span>
        </span>
        <IconChevronRight className="text-brand-600" />
      </Link>

      {(s['portal.contact_phone'] || s['portal.contact_email']) && (
        <section className="card p-4 text-sm">
          <h2 className="font-semibold text-navy-900">{tr('ช่องทางติดต่อ', 'Contact us')}</h2>
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-slate-600">
            {s['portal.contact_phone'] && (
              <a href={`tel:${s['portal.contact_phone']}`} className="inline-flex items-center gap-2 hover:text-brand-700">
                <IconPhone size={18} /> {s['portal.contact_phone']}
              </a>
            )}
            {s['portal.contact_email'] && (
              <a href={`mailto:${s['portal.contact_email']}`} className="inline-flex items-center gap-2 hover:text-brand-700">
                <IconMail size={18} /> {s['portal.contact_email']}
              </a>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
