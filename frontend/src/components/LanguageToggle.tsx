import { useI18n } from '../i18n'
import { cx } from './ui'

export function LanguageToggle({ dark }: { dark?: boolean }) {
  const { lang, setLang } = useI18n()
  return (
    <div
      className={cx(
        'inline-flex rounded-full p-0.5 text-xs font-semibold',
        dark ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-600',
      )}
      role="group"
      aria-label="Language"
    >
      {(['th', 'en'] as const).map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => setLang(l)}
          aria-pressed={lang === l}
          className={cx(
            'rounded-full px-3 py-1 transition',
            lang === l && (dark ? 'bg-white text-navy-900' : 'bg-white text-navy-900 shadow-sm'),
          )}
        >
          {l === 'th' ? 'ไทย' : 'EN'}
        </button>
      ))}
    </div>
  )
}
