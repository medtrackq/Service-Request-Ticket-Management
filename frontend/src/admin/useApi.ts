import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '../api/client'

/** GET `path` (re-fetches when path changes); `null` path disables fetching. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(!!path)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!path) return
    const ctrl = new AbortController()
    setLoading(true)
    setError(null)
    api
      .get<T>(path, { signal: ctrl.signal })
      .then((d) => setData(d))
      .catch((e) => {
        if ((e as Error)?.name === 'AbortError') return
        setError(e instanceof ApiError ? e : new ApiError(0, 'ERROR', String(e)))
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false)
      })
    return () => ctrl.abort()
  }, [path, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, setData, error, loading, reload }
}
