import { useEffect, useState } from 'react'
import { api, type ApiError } from '../api/client'
import type { PortalConfig } from '../api/types'

let cache: PortalConfig | null = null

export function usePortalConfig() {
  const [data, setData] = useState<PortalConfig | null>(cache)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  useEffect(() => {
    if (cache && nonce === 0) return
    let alive = true
    api
      .get<PortalConfig>('/public/portal')
      .then((d) => {
        cache = d
        if (alive) {
          setData(d)
          setError(null)
        }
      })
      .catch((e: ApiError) => alive && setError(e.message))
    return () => {
      alive = false
    }
  }, [nonce])
  return { data, error, reload: () => setNonce((n) => n + 1) }
}
