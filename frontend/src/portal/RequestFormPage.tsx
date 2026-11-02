import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, api, uploadWithProgress } from '../api/client'
import type { FormFieldDef, PublicForm, SubmissionResult } from '../api/types'
import { FileUploader } from '../components/FileUploader'
import { IconChevronLeft, IconShield, RequestTypeIcon } from '../components/Icons'
import { ErrorBox, Loading, Spinner, cx } from '../components/ui'
import { useI18n } from '../i18n'
import { newIdempotencyKey, revokeItems, type UploadItem } from '../lib/files'
import { DynamicField } from './DynamicField'
import { normaliseValue, validateField } from '../lib/validation'

export const LAST_SUBMISSION_KEY = 'buc.lastSubmission'

type Step = 0 | 1 | 2

export function RequestFormPage() {
  const { slug = '' } = useParams()
  const navigate = useNavigate()
  const { tr, pick } = useI18n()
  const [form, setForm] = useState<PublicForm | null>(null)
  const [loadError, setLoadError] = useState<ApiError | null>(null)
  const [nonce, setNonce] = useState(0)
  const [values, setValues] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [items, setItems] = useState<UploadItem[]>([])
  const [step, setStep] = useState<Step>(0)
  const [consent, setConsent] = useState(false)
  const [honeypot, setHoneypot] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [submitError, setSubmitError] = useState<ApiError | null>(null)
  const idem = useRef<{ key: string; sig: string } | null>(null)
  const topRef = useRef<HTMLDivElement>(null)
  const itemsRef = useRef(items)
  itemsRef.current = items

  useEffect(() => {
    let alive = true
    setForm(null)
    setLoadError(null)
    api
      .get<PublicForm>(`/public/forms/${encodeURIComponent(slug)}`)
      .then((f) => {
        if (!alive) return
        setForm(f)
        // Keep values that still exist when a newer form version is loaded.
        setValues((prev) => Object.fromEntries(f.fields.filter((x) => x.key in prev).map((x) => [x.key, prev[x.key]])))
      })
      .catch((e: ApiError) => alive && setLoadError(e))
    return () => {
      alive = false
    }
  }, [slug, nonce])

  // Release object URLs when leaving the page.
  useEffect(() => () => revokeItems(itemsRef.current), [])

  const fileField = form?.fields.find((f) => f.field_type === 'file') ?? null
  const stepFields = useMemo(() => {
    const fs = form?.fields ?? []
    return {
      0: fs.filter((f) => f.section === 'customer' && f.field_type !== 'file'),
      1: fs.filter((f) => f.section !== 'customer' && f.field_type !== 'file'),
    } as Record<0 | 1, FormFieldDef[]>
  }, [form])

  const scrollTop = () => topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  const validateStep = useCallback(
    (s: 0 | 1, lang: 'th' | 'en') => {
      const errs: Record<string, string> = {}
      for (const f of stepFields[s]) {
        const e = validateField(f, values[f.key], lang)
        if (e) errs[f.key] = e
      }
      return errs
    },
    [stepFields, values],
  )

  const { lang } = useI18n()

  function focusFirstError(errs: Record<string, string>) {
    const first = Object.keys(errs)[0]
    if (!first) return
    requestAnimationFrame(() => {
      const el = document.querySelector<HTMLElement>(`[data-field="${first}"] input, [data-field="${first}"] select, [data-field="${first}"] textarea`)
      el?.focus()
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }

  function goNext() {
    if (step === 2) return
    const errs = validateStep(step, lang)
    setErrors((prev) => {
      const next = { ...prev }
      for (const f of stepFields[step]) delete next[f.key]
      return { ...next, ...errs }
    })
    if (Object.keys(errs).length) {
      focusFirstError(errs)
      return
    }
    setStep((s) => (s + 1) as Step)
    scrollTop()
  }

  function goBack() {
    if (step === 0) return
    setStep((s) => (s - 1) as Step)
    scrollTop()
  }

  function setValue(key: string, v: string) {
    setValues((prev) => ({ ...prev, [key]: v }))
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: '' }))
  }

  async function submit() {
    if (!form || submitting) return
    setSubmitError(null)
    const all = { ...validateStep(0, lang), ...validateStep(1, lang) }
    if (!consent) all.privacy_consent = tr('กรุณายอมรับประกาศความเป็นส่วนตัว', 'Please accept the privacy notice')
    if (Object.keys(all).length) {
      setErrors(all)
      const firstStep: Step = stepFields[0].some((f) => all[f.key]) ? 0 : stepFields[1].some((f) => all[f.key]) ? 1 : 2
      setStep(firstStep)
      focusFirstError(all)
      return
    }
    const payloadValues: Record<string, unknown> = {}
    for (const f of form.fields) {
      if (f.field_type === 'file') continue
      payloadValues[f.key] = normaliseValue(f, values[f.key])
    }
    // Same content => same Idempotency-Key, so retries / double taps return the same ticket.
    const sig = JSON.stringify([payloadValues, items.map((i) => i.sig)])
    if (!idem.current || idem.current.sig !== sig) idem.current = { key: newIdempotencyKey(), sig }

    const fd = new FormData()
    fd.append(
      'payload',
      JSON.stringify({ form_definition_id: form.id, values: payloadValues, privacy_consent: consent, website: honeypot }),
    )
    for (const it of items) fd.append('files', it.file, it.file.name)

    setSubmitting(true)
    setProgress(0)
    try {
      const { data } = await uploadWithProgress<SubmissionResult>(
        `/public/requests/${encodeURIComponent(slug)}`,
        fd,
        { 'Idempotency-Key': idem.current.key },
        setProgress,
      )
      try {
        sessionStorage.setItem(LAST_SUBMISSION_KEY, JSON.stringify(data))
      } catch {
        /* storage unavailable */
      }
      navigate(`/request/${slug}/success`, { state: { result: data }, replace: true })
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, 'NETWORK_ERROR', String(e))
      setSubmitError(err)
      if (err.code === 'VALIDATION_ERROR' && Object.keys(err.fields).length) {
        setErrors(err.fields)
        const keys = Object.keys(err.fields)
        const target: Step = stepFields[0].some((f) => keys.includes(f.key))
          ? 0
          : stepFields[1].some((f) => keys.includes(f.key)) || keys.includes('attachments')
            ? 1
            : 2
        setStep(target)
        focusFirstError(err.fields)
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (loadError) {
    return (
      <div className="space-y-4">
        <ErrorBox
          message={loadError.status === 404 ? tr('ไม่พบแบบฟอร์มที่ต้องการ', 'Form not found') : loadError.message}
          onRetry={loadError.status === 404 ? undefined : () => setNonce((n) => n + 1)}
        />
        <Link to="/" className="btn-secondary">
          {tr('กลับหน้าหลัก', 'Back to home')}
        </Link>
      </div>
    )
  }
  if (!form) return <Loading />

  const steps = [tr('ข้อมูลผู้ติดต่อ', 'Contact'), tr('รายละเอียดคำขอ', 'Request details'), tr('ตรวจสอบและส่ง', 'Review & submit')]

  return (
    <div ref={topRef} className="scroll-mt-20 space-y-4">
      <Link to="/" className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
        <IconChevronLeft size={16} /> {tr('เลือกบริการอื่น', 'Choose another service')}
      </Link>

      <div className="flex items-center gap-3">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-navy-900 text-white">
          <RequestTypeIcon icon={form.request_type.icon} size={26} />
        </span>
        <div className="min-w-0">
          <h1 className="text-xl leading-tight font-bold text-navy-900">{pick(form.request_type, 'name')}</h1>
          <p className="text-sm text-slate-500">{pick(form, 'title')}</p>
        </div>
      </div>

      <ol className="grid grid-cols-3 gap-2" aria-label={tr('ขั้นตอน', 'Steps')}>
        {steps.map((label, i) => (
          <li key={label} aria-current={i === step ? 'step' : undefined}>
            <div className={cx('h-1.5 rounded-full', i <= step ? 'bg-brand-600' : 'bg-slate-300')} />
            <p className={cx('mt-1.5 text-xs leading-tight', i === step ? 'font-semibold text-navy-900' : 'text-slate-500')}>
              <span className="mr-1">{i + 1}.</span>
              {label}
            </p>
          </li>
        ))}
      </ol>

      <form
        noValidate
        className="card space-y-5 p-4 sm:p-6"
        onSubmit={(e) => {
          e.preventDefault()
          if (step < 2) goNext()
          else void submit()
        }}
      >
        {/* Honeypot: invisible to people, often filled by bots. */}
        <div className="sr-only-hp" aria-hidden="true">
          <label htmlFor="website">Website</label>
          <input id="website" name="website" tabIndex={-1} autoComplete="off" value={honeypot} onChange={(e) => setHoneypot(e.target.value)} />
        </div>

        {step === 0 && (
          <>
            <h2 className="text-base font-semibold text-navy-900">{steps[0]}</h2>
            {stepFields[0].map((f) => (
              <DynamicField key={f.key} field={f} value={values[f.key] ?? ''} error={errors[f.key]} onChange={(v) => setValue(f.key, v)} />
            ))}
          </>
        )}

        {step === 1 && (
          <>
            <h2 className="text-base font-semibold text-navy-900">{steps[1]}</h2>
            {stepFields[1].map((f) => (
              <DynamicField key={f.key} field={f} value={values[f.key] ?? ''} error={errors[f.key]} onChange={(v) => setValue(f.key, v)} />
            ))}
            {fileField && form.file_rules.max_files > 0 && (
              <FileUploader
                label={pick(fileField, 'label')}
                help={pick(fileField, 'help')}
                rules={form.file_rules}
                items={items}
                onChange={setItems}
                error={errors.attachments}
              />
            )}
          </>
        )}

        {step === 2 && (
          <ReviewStep
            form={form}
            values={values}
            items={items}
            consent={consent}
            setConsent={(v) => {
              setConsent(v)
              if (v) setErrors((p) => ({ ...p, privacy_consent: '' }))
            }}
            consentError={errors.privacy_consent}
            onEdit={(s) => {
              setStep(s)
              scrollTop()
            }}
          />
        )}

        {submitError && submitError.code !== 'VALIDATION_ERROR' && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <p className="font-medium">
              {submitError.code === 'FORM_VERSION_CHANGED'
                ? tr('แบบฟอร์มมีการปรับปรุง กรุณาโหลดแบบฟอร์มใหม่แล้วส่งอีกครั้ง', 'The form has been updated. Please reload it and submit again.')
                : submitError.code === 'NETWORK_ERROR'
                  ? tr('ส่งข้อมูลไม่สำเร็จเนื่องจากการเชื่อมต่อ กดส่งอีกครั้งได้อย่างปลอดภัย ระบบจะไม่สร้างคำขอซ้ำ', 'Connection problem. You can safely press submit again — no duplicate request will be created.')
                  : submitError.message}
            </p>
            {submitError.code === 'FORM_VERSION_CHANGED' && (
              <button type="button" className="btn-secondary mt-2" onClick={() => setNonce((n) => n + 1)}>
                {tr('โหลดแบบฟอร์มใหม่', 'Reload form')}
              </button>
            )}
          </div>
        )}
        {submitError?.code === 'VALIDATION_ERROR' && (
          <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {submitError.message}
          </p>
        )}

        <div className="safe-bottom sticky bottom-0 -mx-4 flex gap-3 border-t border-slate-200 bg-white/95 px-4 pt-3 backdrop-blur sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:px-0 sm:pb-0">
          {step > 0 && (
            <button type="button" className="btn-secondary min-h-12 flex-1 sm:flex-none" onClick={goBack} disabled={submitting}>
              {tr('ย้อนกลับ', 'Back')}
            </button>
          )}
          {step < 2 ? (
            <button type="submit" className="btn-primary min-h-12 flex-[2] sm:flex-none sm:px-8" data-testid="next-step">
              {tr('ถัดไป', 'Next')}
            </button>
          ) : (
            <button type="submit" className="btn-primary min-h-12 flex-[2] sm:flex-none sm:px-8" disabled={submitting} data-testid="submit-request">
              {submitting ? (
                <>
                  <Spinner className="h-4 w-4" />
                  {items.length > 0 && progress > 0 && progress < 1
                    ? tr(`กำลังอัปโหลด ${Math.round(progress * 100)}%`, `Uploading ${Math.round(progress * 100)}%`)
                    : tr('กำลังส่ง...', 'Submitting...')}
                </>
              ) : (
                tr('ส่งคำขอ', 'Submit request')
              )}
            </button>
          )}
        </div>
      </form>
    </div>
  )
}

function ReviewStep({
  form,
  values,
  items,
  consent,
  setConsent,
  consentError,
  onEdit,
}: {
  form: PublicForm
  values: Record<string, string>
  items: UploadItem[]
  consent: boolean
  setConsent: (v: boolean) => void
  consentError?: string
  onEdit: (s: Step) => void
}) {
  const { tr, pick } = useI18n()
  const display = (f: FormFieldDef) => {
    const v = values[f.key]
    if (!v) return '-'
    if (f.field_type === 'select') {
      const o = f.options?.find((x) => x.value === v)
      return o ? pick(o, 'label') : v
    }
    return v
  }
  const groups: { title: string; step: Step; fields: FormFieldDef[] }[] = [
    { title: tr('ข้อมูลผู้ติดต่อ', 'Contact'), step: 0, fields: form.fields.filter((f) => f.section === 'customer' && f.field_type !== 'file') },
    { title: tr('รายละเอียดคำขอ', 'Request details'), step: 1, fields: form.fields.filter((f) => f.section !== 'customer' && f.field_type !== 'file') },
  ]
  return (
    <div className="space-y-5">
      <h2 className="text-base font-semibold text-navy-900">{tr('ตรวจสอบข้อมูลก่อนส่ง', 'Review your request')}</h2>
      {groups.map((g) => (
        <div key={g.title} className="rounded-lg border border-slate-200">
          <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-3 py-2">
            <h3 className="text-sm font-semibold text-slate-700">{g.title}</h3>
            <button type="button" className="text-sm font-medium text-brand-700 hover:underline" onClick={() => onEdit(g.step)}>
              {tr('แก้ไข', 'Edit')}
            </button>
          </div>
          <dl className="divide-y divide-slate-100 px-3">
            {g.fields
              .filter((f) => values[f.key])
              .map((f) => (
                <div key={f.key} className="grid grid-cols-1 gap-0.5 py-2 text-sm sm:grid-cols-[minmax(0,12rem)_minmax(0,1fr)] sm:gap-3">
                  <dt className="text-slate-500">{pick(f, 'label')}</dt>
                  <dd className="break-words whitespace-pre-line text-slate-900">{display(f)}</dd>
                </div>
              ))}
          </dl>
        </div>
      ))}
      {items.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-semibold text-slate-700">
            {tr('ไฟล์แนบ', 'Attachments')} ({items.length})
          </p>
          <ul className="grid grid-cols-4 gap-2 sm:grid-cols-6">
            {items.map((it) => (
              <li key={it.id} className="overflow-hidden rounded-md border border-slate-200 bg-white">
                {it.previewUrl ? (
                  <img src={it.previewUrl} alt={it.file.name} className="aspect-square w-full object-cover" />
                ) : (
                  <div className="flex aspect-square items-center justify-center p-1 text-center text-[10px] break-all text-slate-600">{it.file.name}</div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className={cx('rounded-lg border p-3', consentError ? 'border-red-300 bg-red-50' : 'border-brand-100 bg-brand-50')} data-field="privacy_consent">
        <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 h-5 w-5 shrink-0 accent-brand-600"
            data-testid="privacy-consent"
          />
          <span>
            <IconShield size={16} className="mr-1 inline text-brand-600" />
            {tr('ข้าพเจ้าได้อ่านและยอมรับ', 'I have read and accept the ')}{' '}
            <Link to="/privacy" target="_blank" className="font-medium text-brand-700 underline">
              {tr('ประกาศความเป็นส่วนตัว', 'privacy notice')}
            </Link>{' '}
            {tr('และยินยอมให้บริษัทใช้ข้อมูลเพื่อดำเนินการตามคำขอนี้', 'and consent to the use of my data to handle this request')}
          </span>
        </label>
        {consentError && <p className="mt-1 text-sm text-red-600">{consentError}</p>}
      </div>
    </div>
  )
}

