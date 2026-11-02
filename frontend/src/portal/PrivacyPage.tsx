import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ApiError } from '../api/client'
import type { PrivacyNotice } from '../api/types'
import { IconShield } from '../components/Icons'
import { ErrorBox, Loading } from '../components/ui'
import { useI18n } from '../i18n'

export function PrivacyPage() {
  const { tr, lang } = useI18n()
  const [data, setData] = useState<PrivacyNotice | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    api.get<PrivacyNotice>('/public/privacy-notice').then(setData).catch((e: ApiError) => setError(e.message))
  }, [])
  if (error) return <ErrorBox message={error} />
  if (!data) return <Loading />
  return (
    <article className="card p-5 sm:p-7">
      <div className="flex items-center gap-3 text-navy-900">
        <IconShield className="text-brand-600" size={26} />
        <h1 className="text-xl font-bold">{tr('ประกาศความเป็นส่วนตัว', 'Privacy Notice')}</h1>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {tr('เวอร์ชัน', 'Version')} {data.version}
      </p>
      <div className="mt-4 text-[15px] leading-7 whitespace-pre-line text-slate-700">{lang === 'en' ? data.text_en : data.text_th}</div>
      <Link to="/" className="btn-secondary mt-6">
        {tr('กลับหน้าหลัก', 'Back to home')}
      </Link>
    </article>
  )
}
