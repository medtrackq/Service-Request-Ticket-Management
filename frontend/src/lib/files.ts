// Client-side file checks and preparation. The backend re-validates everything (magic bytes, Pillow decode).
import type { Lang } from '../api/types'

export type SniffedType = 'image/jpeg' | 'image/png' | 'application/pdf'

export interface UploadItem {
  id: string
  file: File
  previewUrl: string | null
  kind: 'image' | 'pdf'
  mime: SniffedType
  /** Signature of the originally selected file (dedupe). */
  sig: string
}

export async function sniffType(file: Blob): Promise<SniffedType | null> {
  const buf = new Uint8Array(await file.slice(0, 8).arrayBuffer())
  if (buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return 'image/jpeg'
  if (buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47) return 'image/png'
  if (buf[0] === 0x25 && buf[1] === 0x50 && buf[2] === 0x44 && buf[3] === 0x46) return 'application/pdf'
  return null
}

function looksLikeImage(file: File) {
  return file.type.startsWith('image/') || /\.(heic|heif|webp|gif|bmp|avif)$/i.test(file.name)
}

async function decodeImage(file: File): Promise<{ draw: (ctx: CanvasRenderingContext2D) => void; w: number; h: number }> {
  if (typeof createImageBitmap === 'function') {
    try {
      const bmp = await createImageBitmap(file)
      return { draw: (ctx) => ctx.drawImage(bmp, 0, 0), w: bmp.width, h: bmp.height }
    } catch {
      /* fall back to <img> (Safari decodes HEIC through <img>) */
    }
  }
  const url = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error('decode failed'))
      el.src = url
    })
    return { draw: (ctx) => ctx.drawImage(img, 0, 0), w: img.naturalWidth, h: img.naturalHeight }
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}

/** Convert a browser-decodable image (e.g. HEIC on iOS) to JPEG. */
export async function convertToJpeg(file: File): Promise<File> {
  const { draw, w, h } = await decodeImage(file)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas unavailable')
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, w, h)
  draw(ctx)
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
  if (!blob) throw new Error('encode failed')
  const name = file.name.replace(/\.[^.]+$/, '') + '.jpg'
  return new File([blob], name, { type: 'image/jpeg', lastModified: file.lastModified })
}

export interface PrepareResult {
  item?: UploadItem
  error?: string
}

let seq = 0

/** Validate (and if needed convert) one selected file. */
export async function prepareFile(file: File, accept: string[], maxSizeMb: number, lang: Lang): Promise<PrepareResult> {
  const t = (th: string, en: string) => (lang === 'en' ? en : th)
  let f = file
  let mime = await sniffType(f)
  if ((!mime || !accept.includes(mime)) && looksLikeImage(f) && accept.some((a) => a.startsWith('image/'))) {
    try {
      f = await convertToJpeg(f)
      mime = 'image/jpeg'
    } catch {
      return { error: t(`ไฟล์ ${file.name} ไม่สามารถเปิดได้`, `${file.name} could not be read`) }
    }
  }
  if (!mime || !accept.includes(mime)) {
    const allowed = accept.map((a) => (a === 'image/jpeg' ? 'JPG/JPEG' : a === 'image/png' ? 'PNG' : 'PDF')).join(', ')
    return { error: t(`ไฟล์ ${file.name} ไม่ใช่ประเภทที่รองรับ (รองรับ ${allowed})`, `${file.name}: unsupported type (allowed ${allowed})`) }
  }
  if (f.size === 0) return { error: t(`ไฟล์ ${file.name} ว่างเปล่า`, `${file.name} is empty`) }
  if (f.size > maxSizeMb * 1024 * 1024) {
    return { error: t(`ไฟล์ ${file.name} มีขนาดเกิน ${maxSizeMb} MB`, `${file.name} is larger than ${maxSizeMb} MB`) }
  }
  const isImage = mime !== 'application/pdf'
  seq += 1
  return {
    item: {
      id: `${Date.now().toString(36)}-${seq}`,
      file: f,
      previewUrl: isImage ? URL.createObjectURL(f) : null,
      kind: isImage ? 'image' : 'pdf',
      mime,
      sig: fileSignature(file),
    },
  }
}

export function fileSignature(f: File) {
  return `${f.name}|${f.size}|${f.lastModified}`
}

export function revokeItems(items: UploadItem[]) {
  for (const it of items) if (it.previewUrl) URL.revokeObjectURL(it.previewUrl)
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

/** Idempotency key matching ^[A-Za-z0-9_-]{16,64}$ */
export function newIdempotencyKey(): string {
  const c = globalThis.crypto as Crypto | undefined
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()
  const bytes = new Uint8Array(16)
  if (c && typeof c.getRandomValues === 'function') c.getRandomValues(bytes)
  else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256)
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}
