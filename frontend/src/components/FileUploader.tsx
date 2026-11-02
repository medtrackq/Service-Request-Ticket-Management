import { useRef, useState, type Dispatch, type SetStateAction } from 'react'
import type { FileRules } from '../api/types'
import { useI18n } from '../i18n'
import { formatBytes, prepareFile, type UploadItem } from '../lib/files'
import { IconCamera, IconFile, IconImage, IconRefresh, IconX } from './Icons'
import { Spinner, cx } from './ui'

interface Props {
  label: string
  help?: string | null
  rules: FileRules
  items: UploadItem[]
  onChange: Dispatch<SetStateAction<UploadItem[]>>
  /** Lower the effective maximum (e.g. files already attached to a ticket). */
  maxFiles?: number
  error?: string | null
  compact?: boolean
}

/**
 * Multi-file / camera uploader used by the customer forms.
 * Works inside the LINE in-app browser: plain <input type="file"> elements triggered by buttons,
 * one with `capture` for the camera and one multi-select for the gallery.
 */
export function FileUploader({ label, help, rules, items, onChange, maxFiles, error, compact }: Props) {
  const { tr, lang } = useI18n()
  const galleryRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const replaceRef = useRef<HTMLInputElement>(null)
  const replaceTarget = useRef<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<string[]>([])

  const max = Math.max(0, maxFiles ?? rules.max_files)
  const imagesOnly = rules.accept.every((a) => a.startsWith('image/'))
  const allowsImages = rules.accept.some((a) => a.startsWith('image/'))
  const full = items.length >= max
  const unit = imagesOnly ? tr('ภาพ', 'images') : tr('ไฟล์', 'files')

  async function handle(list: FileList | null, replaceId: string | null) {
    if (!list || list.length === 0) return
    setBusy(true)
    const notes: string[] = []
    const files = Array.from(list)
    const current = items
    const existingSigs = new Set(current.filter((i) => i.id !== replaceId).map((i) => i.sig))
    const remaining = replaceId ? 1 : max - current.length
    const accepted: UploadItem[] = []
    let overflow = 0
    for (const f of files) {
      if (accepted.length >= remaining) {
        overflow += 1
        continue
      }
      const sig = `${f.name}|${f.size}|${f.lastModified}`
      if (existingSigs.has(sig)) {
        notes.push(tr(`ไฟล์ ${f.name} ถูกเลือกไว้แล้ว`, `${f.name} is already selected`))
        continue
      }
      const res = await prepareFile(f, rules.accept, rules.max_size_mb, lang)
      if (res.error) notes.push(res.error)
      else if (res.item) {
        existingSigs.add(res.item.sig)
        accepted.push(res.item)
      }
    }
    if (overflow > 0) {
      notes.unshift(
        tr(
          `แนบได้สูงสุด ${max} ${unit} — ไม่ได้เพิ่มไฟล์ส่วนที่เกินจำนวน ${overflow} ไฟล์`,
          `You can attach up to ${max} ${unit}. ${overflow} extra file(s) were not added.`,
        ),
      )
    }
    if (accepted.length) {
      onChange((prev) => {
        if (replaceId) {
          return prev.map((it) => {
            if (it.id !== replaceId) return it
            if (it.previewUrl) URL.revokeObjectURL(it.previewUrl)
            return accepted[0]
          })
        }
        const room = Math.max(0, max - prev.length)
        const add = accepted.slice(0, room)
        for (const extra of accepted.slice(room)) if (extra.previewUrl) URL.revokeObjectURL(extra.previewUrl)
        return [...prev, ...add]
      })
    }
    setMessages(notes)
    setBusy(false)
  }

  function remove(id: string) {
    onChange((prev) => {
      const it = prev.find((x) => x.id === id)
      if (it?.previewUrl) URL.revokeObjectURL(it.previewUrl)
      return prev.filter((x) => x.id !== id)
    })
    setMessages([])
  }

  function startReplace(id: string) {
    replaceTarget.current = id
    replaceRef.current?.click()
  }

  return (
    <div>
      <p className="label">{label}</p>
      <div
        className={cx(
          'rounded-xl border-2 border-dashed bg-slate-50/70 p-3 sm:p-4',
          error ? 'border-red-300' : 'border-slate-300',
        )}
      >
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn-primary min-h-11 flex-1 sm:flex-none"
            disabled={full || busy}
            onClick={() => galleryRef.current?.click()}
            data-testid="add-files"
          >
            {busy ? <Spinner className="h-4 w-4" /> : imagesOnly ? <IconImage size={18} /> : <IconFile size={18} />}
            <span data-testid="upload-counter">
              {imagesOnly ? '📷 ' : '📎 '}
              {imagesOnly ? tr('เพิ่มรูปภาพ', 'Add photos') : tr('เพิ่มไฟล์', 'Add files')} ({items.length}/{max})
            </span>
          </button>
          {allowsImages && (
            <button
              type="button"
              className="btn-secondary min-h-11 flex-1 sm:flex-none"
              disabled={full || busy}
              onClick={() => cameraRef.current?.click()}
            >
              <IconCamera size={18} /> {tr('ถ่ายรูป', 'Take photo')}
            </button>
          )}
        </div>
        <p className="mt-2 text-sm font-medium text-slate-700">
          {imagesOnly ? tr(`แนบรูปภาพได้สูงสุด ${max} ภาพ`, `Up to ${max} images`) : tr(`แนบไฟล์ได้สูงสุด ${max} ไฟล์`, `Up to ${max} files`)}
          <span className="font-normal text-slate-500">
            {' '}
            · {rules.accept.map((a) => (a === 'image/jpeg' ? 'JPG' : a === 'image/png' ? 'PNG' : 'PDF')).join(', ')} ·{' '}
            {tr(`ไม่เกิน ${rules.max_size_mb} MB ต่อไฟล์`, `max ${rules.max_size_mb} MB each`)}
          </span>
        </p>
        {help && !compact && <p className="mt-1 text-sm text-slate-500">{help}</p>}

        {items.length > 0 && (
          <ul className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5" data-testid="upload-previews">
            {items.map((it, idx) => (
              <li key={it.id} className="group relative overflow-hidden rounded-lg border border-slate-200 bg-white">
                {it.kind === 'image' && it.previewUrl ? (
                  <img src={it.previewUrl} alt={`${idx + 1}. ${it.file.name}`} className="aspect-square w-full object-cover" />
                ) : (
                  <div className="flex aspect-square w-full flex-col items-center justify-center gap-1 p-2 text-center text-red-700">
                    <IconFile size={28} />
                    <span className="line-clamp-2 text-[11px] break-all text-slate-600">{it.file.name}</span>
                  </div>
                )}
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-1.5 pt-4 pb-1 text-[10px] text-white">
                  {formatBytes(it.file.size)}
                </div>
                <button
                  type="button"
                  onClick={() => remove(it.id)}
                  className="absolute top-1 right-1 grid h-8 w-8 place-items-center rounded-full bg-black/60 text-white hover:bg-red-600"
                  aria-label={tr(`ลบไฟล์ ${it.file.name}`, `Remove ${it.file.name}`)}
                  data-testid="remove-file"
                >
                  <IconX size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => startReplace(it.id)}
                  className="absolute top-1 left-1 grid h-8 w-8 place-items-center rounded-full bg-black/50 text-white hover:bg-brand-600"
                  aria-label={tr(`เปลี่ยนไฟล์ ${it.file.name}`, `Replace ${it.file.name}`)}
                >
                  <IconRefresh size={15} />
                </button>
              </li>
            ))}
          </ul>
        )}

        <input
          ref={galleryRef}
          type="file"
          accept={rules.accept.join(',')}
          multiple
          className="hidden"
          data-testid="gallery-input"
          onChange={(e) => {
            void handle(e.target.files, null)
            e.target.value = ''
          }}
        />
        {allowsImages && (
          <input
            ref={cameraRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            data-testid="camera-input"
            onChange={(e) => {
              void handle(e.target.files, null)
              e.target.value = ''
            }}
          />
        )}
        <input
          ref={replaceRef}
          type="file"
          accept={rules.accept.join(',')}
          className="hidden"
          onChange={(e) => {
            void handle(e.target.files, replaceTarget.current)
            replaceTarget.current = null
            e.target.value = ''
          }}
        />
      </div>
      {messages.length > 0 && (
        <ul className="mt-2 space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="alert" data-testid="upload-warning">
          {messages.map((m, i) => (
            <li key={i}>⚠️ {m}</li>
          ))}
        </ul>
      )}
      {error && (
        <p className="mt-1 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
