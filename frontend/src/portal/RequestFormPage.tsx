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

/** Single-page request form: all sections on one screen, one submit button. */
export function RequestFormPage() {
  const { slug = '' } = useParams()
  const navigate = useNavigate()
  const { tr, pick, lang } = useI18n()
  const [form, setForm] = useState<PublicForm | null>(null)
  const [loadError, setLoadError] = useState<ApiError | null>(null)
  const [nonce, setNonce] = useState(0)
  const [values, setValues] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [items, setItems] = useState<UploadItem[]>([])
  const [consent, setConsent] = useState(false)
  const [honeypot, setHoneypot] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [submitError, setSubmitError] = useState<ApiError | null>(null)
  const idem = useRef<{ key: string; sig: string } | null>(null)
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
  const sections = useMemo(() => {
    const fs = (form?.fields ?? []).filter((f) => f.field_type !== 'file')
    return {
      contact: fs.filter((f) => f.section === 'customer'),
      request: fs.filter((f) => f.section !== 'customer'),
    }
  }, [form])

  /** Error keys in on-screen order, so we always jump to the top-most problem. */
  const errorOrder = useMemo(
    () => [...sections.contact, ...sections.request].map((f) => f.key).concat(['attachments', 'privacy_consent']),
    [sections],
  )

  const validateAll = useCallback(() => {
    const errs: Record<string, string> = {}
    for (const f of [...sections.contact, ...sections.request]) {
      const e = validateField(f, values[f.key], lang)
      if (e) errs[f.key] = e
    }
    if (!consent) errs.privacy_consent = tr('กรุณายอมรับประกาศความเป็นส่วนตัว', 'Please accept the privacy notice')
    return errs
  }, [sections, values, consent, lang, tr])

  function focusFirstError(errs: Record<string, string>) {
    const first = errorOrder.find((k) => errs[k]) ?? Object.keys(errs)[0]
    if (!first) return
    requestAnimationFrame(() => {
      const box = document.querySelector<HTMLElement>(`[data-field="${first}"]`)
      const input = box?.querySelector<HTMLElement>('input:not([type=file]), select, textarea')
      box?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      input?.focus({ preventScroll: true })
    })
  }

  function setValue(key: string, v: string) {
    setValues((prev) => ({ ...prev, [key]: v }))
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: '' }))
  }

  async function submit() {
    if (!form || submitting) return
    setSubmitError(null)
    const all = validateAll()
    if (Object.keys(all).length) {
      setErrors(all)
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

  const renderField = (f: FormFieldDef) => (
    <DynamicField key={f.key} field={f} value={values[f.key] ?? ''} error={errors[f.key]} onChange={(v) => setValue(f.key, v)} />
  )
  const errorCount = Object.values(errors).filter(Boolean).length

  return (
    <div className="space-y-4">
      <Link to="/" className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
        <IconChevronLeft size={16} /> {tr('เลือกบริการอื่น', 'Choose another service')}
      </Link>

      <div className="flex items-center gap-3">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-navy-900 text-white">
          <RequestTypeIcon icon={form.request_type.icon} size={26} />
        </span>
        <div className="min-w-0">
          <h1 className="text-xl leading-tight font-bold text-navy-900">{pick(form.request_type, 'name')}</h1>
          <p className="text-sm text-slate-500">
            {tr('กรอกข้อมูลในหน้านี้แล้วกด "ส่งคำขอ" ด้านล่าง', 'Fill in this page and press "Submit request" below')}
            <span className="text-red-600"> *</span> {tr('= จำเป็น', '= required')}
          </p>
        </div>
      </div>

      <form
        noValidate
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        {/* Honeypot: invisible to people, often filled by bots. */}
        <div className="sr-only-hp" aria-hidden="true">
          <label htmlFor="website">Website</label>
          <input id="website" name="website" tabIndex={-1} autoComplete="off" value={honeypot} onChange={(e) => setHoneypot(e.target.value)} />
        </div>

        {sections.contact.length > 0 && (
          <section className="card space-y-5 p-4 sm:p-6" aria-labelledby="sec-contact">
            <h2 id="sec-contact" className="text-base font-semibold text-navy-900">
              {tr('ข้อมูลผู้ติดต่อ', 'Contact information')}
            </h2>
            {sections.contact.map(renderField)}
          </section>
        )}

        {sections.request.length > 0 && (
          <section className="card space-y-5 p-4 sm:p-6" aria-labelledby="sec-request">
            <h2 id="sec-request" className="text-base font-semibold text-navy-900">
              {tr('รายละเอียดคำขอ', 'Request details')}
            </h2>
            {sections.request.map(renderField)}
          </section>
        )}

        {fileField && form.file_rules.max_files > 0 && (
          <section className="card p-4 sm:p-6" data-field="attachments">
            <FileUploader
              label={pick(fileField, 'label')}
              help={pick(fileField, 'help')}
              rules={form.file_rules}
              items={items}
              onChange={setItems}
              error={errors.attachments}
            />
          </section>
        )}

        <div
          className={cx('card p-4', errors.privacy_consent ? 'border-red-300 bg-red-50' : 'border-brand-100 bg-brand-50')}
          data-field="privacy_consent"
        >
          <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => {
                setConsent(e.target.checked)
                if (e.target.checked) setErrors((p) => ({ ...p, privacy_consent: '' }))
              }}
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
          {errors.privacy_consent && <p className="mt-1 text-sm text-red-600">{errors.privacy_consent}</p>}
        </div>

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

        <div className="safe-bottom sticky bottom-0 z-10 -mx-4 border-t border-slate-200 bg-white/95 px-4 pt-3 backdrop-blur sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:px-0">
          {errorCount > 0 && (
            <p role="alert" className="mb-2 text-center text-sm text-red-600" data-testid="form-error-summary">
              {tr(`กรุณาตรวจสอบข้อมูลที่ไม่ถูกต้อง ${errorCount} รายการ`, `Please fix ${errorCount} highlighted field(s)`)}
            </p>
          )}
          <button
            type="submit"
            className="btn-primary min-h-12 w-full sm:w-auto sm:px-10"
            disabled={submitting}
            data-testid="submit-request"
          >
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
        </div>
      </form>
    </div>
  )
}
