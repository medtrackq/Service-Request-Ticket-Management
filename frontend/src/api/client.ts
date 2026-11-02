/**
 * Minimal fetch wrapper for the BUC API.
 * - Same-origin cookies (staff session is an httpOnly cookie scoped to /api).
 * - CSRF token kept in memory and sent as X-CSRF-Token on every non-GET request.
 * - Errors are normalised to ApiError {status, code, message, fields}.
 */

export const API_BASE = '/api/v1'

export class ApiError extends Error {
  status: number
  code: string
  fields: Record<string, string>
  detail: Record<string, unknown> | null

  constructor(status: number, code: string, message: string, fields?: Record<string, string>, detail?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.fields = fields ?? {}
    this.detail = (detail as Record<string, unknown>) ?? null
  }
}

let csrfToken: string | null = null
export function setCsrfToken(token: string | null) {
  csrfToken = token
}

type AuthFailureHandler = (err: ApiError) => void
let authFailureHandler: AuthFailureHandler | null = null
export function onAuthFailure(handler: AuthFailureHandler | null) {
  authFailureHandler = handler
}

const NETWORK_MESSAGE = 'ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้ กรุณาตรวจสอบอินเทอร์เน็ตแล้วลองใหม่'

function toApiError(status: number, data: unknown): ApiError {
  const detail = (data as { detail?: unknown } | null)?.detail
  if (detail && typeof detail === 'object') {
    const d = detail as { code?: string; message?: string; fields?: Record<string, string> }
    return new ApiError(status, d.code ?? `HTTP_${status}`, d.message ?? `HTTP ${status}`, d.fields, d)
  }
  if (status === 429) return new ApiError(status, 'RATE_LIMITED', 'มีการส่งคำขอบ่อยเกินไป กรุณารอสักครู่แล้วลองใหม่')
  if (status === 413) return new ApiError(status, 'PAYLOAD_TOO_LARGE', 'ขนาดไฟล์รวมใหญ่เกินกำหนด')
  return new ApiError(status, `HTTP_${status}`, typeof detail === 'string' ? detail : `เกิดข้อผิดพลาด (HTTP ${status})`)
}

interface RequestOptions {
  body?: unknown
  form?: FormData
  headers?: Record<string, string>
  signal?: AbortSignal
  /** Do not trigger the global 401 handler (used by /auth/me probing). */
  silentAuth?: boolean
}

async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...opts.headers }
  if (method !== 'GET' && csrfToken) headers['X-CSRF-Token'] = csrfToken
  let body: BodyInit | undefined
  if (opts.form) {
    body = opts.form
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  let res: Response
  try {
    res = await fetch(API_BASE + path, { method, headers, body, credentials: 'same-origin', signal: opts.signal })
  } catch (e) {
    if ((e as Error)?.name === 'AbortError') throw e
    throw new ApiError(0, 'NETWORK_ERROR', NETWORK_MESSAGE)
  }
  const isJson = (res.headers.get('content-type') ?? '').includes('application/json')
  const data = isJson ? await res.json().catch(() => null) : null
  if (!res.ok) {
    const err = toApiError(res.status, data)
    if (!opts.silentAuth && (res.status === 401 || err.code === 'PASSWORD_CHANGE_REQUIRED')) {
      authFailureHandler?.(err)
    }
    throw err
  }
  return data as T
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) => request<T>('GET', path, opts),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>('POST', path, { ...opts, body }),
  put: <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>('PUT', path, { ...opts, body }),
  patch: <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>('PATCH', path, { ...opts, body }),
  delete: <T>(path: string, opts?: RequestOptions) => request<T>('DELETE', path, opts),
  upload: <T>(path: string, form: FormData, opts?: RequestOptions) => request<T>('POST', path, { ...opts, form }),
}

/** Multipart POST with upload progress (XMLHttpRequest; fetch has no upload progress). */
export function uploadWithProgress<T>(
  path: string,
  form: FormData,
  headers: Record<string, string>,
  onProgress?: (fraction: number) => void,
): Promise<{ status: number; data: T }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', API_BASE + path)
    xhr.withCredentials = false
    xhr.setRequestHeader('Accept', 'application/json')
    for (const [k, v] of Object.entries(headers)) xhr.setRequestHeader(k, v)
    xhr.timeout = 5 * 60 * 1000
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total)
    }
    xhr.onload = () => {
      let data: unknown = null
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : null
      } catch {
        data = null
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve({ status: xhr.status, data: data as T })
      else reject(toApiError(xhr.status, data))
    }
    xhr.onerror = () => reject(new ApiError(0, 'NETWORK_ERROR', NETWORK_MESSAGE))
    xhr.ontimeout = () => reject(new ApiError(0, 'NETWORK_ERROR', NETWORK_MESSAGE))
    xhr.send(form)
  })
}

export function queryString(params: Record<string, string | number | boolean | null | undefined>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    q.set(k, String(v))
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}
