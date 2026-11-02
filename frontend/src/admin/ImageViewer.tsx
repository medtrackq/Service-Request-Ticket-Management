import { useEffect, useState } from 'react'
import type { Attachment } from '../api/types'
import { IconChevronLeft, IconChevronRight, IconDownload, IconX, IconZoom } from '../components/Icons'
import { cx } from '../components/ui'
import { useI18n } from '../i18n'
import { formatDateTime } from '../lib/dates'
import { formatBytes } from '../lib/files'

/** Full-screen image viewer: Esc closes, ←/→ navigate, click/Z toggles zoom. */
export function ImageViewer({ images, index, onClose, onIndex }: { images: Attachment[]; index: number; onClose: () => void; onIndex: (i: number) => void }) {
  const { tr, lang } = useI18n()
  const [zoom, setZoom] = useState(false)
  const img = images[index]

  useEffect(() => setZoom(false), [index])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowRight') onIndex((index + 1) % images.length)
      else if (e.key === 'ArrowLeft') onIndex((index - 1 + images.length) % images.length)
      else if (e.key.toLowerCase() === 'z') setZoom((z) => !z)
    }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [index, images.length, onClose, onIndex])

  if (!img) return null
  return (
    <div className="fixed inset-0 z-[70] flex flex-col bg-black/95 text-white" role="dialog" aria-modal="true" aria-label={tr('ดูรูปภาพ', 'Image viewer')} data-testid="image-viewer">
      <div className="flex items-center gap-3 px-4 py-3 text-sm">
        <span className="font-medium">
          {index + 1} / {images.length}
        </span>
        <span className="min-w-0 flex-1 truncate text-white/80">
          {img.original_filename} · {formatBytes(img.size_bytes)}
          {img.width ? ` · ${img.width}×${img.height}` : ''} · {formatDateTime(img.created_at, lang)}
        </span>
        <button type="button" onClick={() => setZoom((z) => !z)} className="rounded-md p-2 hover:bg-white/10" aria-label="zoom" title={tr('ซูม (Z)', 'Zoom (Z)')}>
          <IconZoom />
        </button>
        <a href={`${img.url}?download=1`} className="rounded-md p-2 hover:bg-white/10" aria-label={tr('ดาวน์โหลด', 'Download')} title={tr('ดาวน์โหลด', 'Download')}>
          <IconDownload />
        </a>
        <button type="button" onClick={onClose} className="rounded-md p-2 hover:bg-white/10" aria-label={tr('ปิด', 'Close')}>
          <IconX />
        </button>
      </div>
      <div className={cx('relative flex-1', zoom ? 'overflow-auto' : 'flex items-center justify-center overflow-hidden')}>
        <img
          src={img.url}
          alt={img.original_filename}
          onClick={() => setZoom((z) => !z)}
          className={cx('select-none', zoom ? 'max-w-none cursor-zoom-out' : 'max-h-full max-w-full cursor-zoom-in object-contain')}
          style={zoom && img.width ? { width: Math.max(img.width, 1200) } : undefined}
          draggable={false}
        />
        {images.length > 1 && (
          <>
            <button
              type="button"
              onClick={() => onIndex((index - 1 + images.length) % images.length)}
              className="fixed top-1/2 left-3 -translate-y-1/2 rounded-full bg-white/15 p-3 hover:bg-white/25"
              aria-label={tr('ก่อนหน้า', 'Previous')}
            >
              <IconChevronLeft size={26} />
            </button>
            <button
              type="button"
              onClick={() => onIndex((index + 1) % images.length)}
              className="fixed top-1/2 right-3 -translate-y-1/2 rounded-full bg-white/15 p-3 hover:bg-white/25"
              aria-label={tr('ถัดไป', 'Next')}
            >
              <IconChevronRight size={26} />
            </button>
          </>
        )}
      </div>
      {images.length > 1 && (
        <div className="flex justify-center gap-2 overflow-x-auto px-4 py-3">
          {images.map((m, i) => (
            <button key={m.id} type="button" onClick={() => onIndex(i)} className={cx('h-14 w-14 shrink-0 overflow-hidden rounded border-2', i === index ? 'border-white' : 'border-transparent opacity-60')}>
              <img src={m.url} alt="" className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
