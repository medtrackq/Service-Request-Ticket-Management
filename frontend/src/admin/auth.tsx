import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError, api, onAuthFailure, setCsrfToken } from '../api/client'
import type { AuthPayload, CurrentUser, Lookups, Permissions } from '../api/types'
import { Loading } from '../components/ui'

interface AuthValue {
  status: 'loading' | 'anonymous' | 'authenticated'
  user: CurrentUser | null
  permissions: Permissions | null
  login: (username: string, password: string) => Promise<AuthPayload>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [status, setStatus] = useState<AuthValue['status']>('loading')
  const [payload, setPayload] = useState<AuthPayload | null>(null)

  const apply = useCallback((p: AuthPayload | null) => {
    setPayload(p)
    setCsrfToken(p?.csrf_token ?? null)
    setStatus(p ? 'authenticated' : 'anonymous')
  }, [])

  const refresh = useCallback(async () => {
    try {
      apply(await api.get<AuthPayload>('/auth/me', { silentAuth: true }))
    } catch {
      apply(null)
    }
  }, [apply])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    onAuthFailure((err: ApiError) => {
      if (err.code === 'PASSWORD_CHANGE_REQUIRED') {
        navigate('/admin/change-password', { replace: true })
        return
      }
      apply(null)
      navigate(`/admin/login?next=${encodeURIComponent(location.pathname + location.search)}`, { replace: true })
    })
    return () => onAuthFailure(null)
  }, [apply, navigate, location.pathname, location.search])

  const value = useMemo<AuthValue>(
    () => ({
      status,
      user: payload?.user ?? null,
      permissions: payload?.permissions ?? null,
      login: async (username, password) => {
        const p = await api.post<AuthPayload>('/auth/login', { username, password }, { silentAuth: true })
        apply(p)
        return p
      },
      logout: async () => {
        try {
          await api.post('/auth/logout', undefined, { silentAuth: true })
        } finally {
          apply(null)
        }
      },
      refresh,
    }),
    [status, payload, apply, refresh],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}

export function RequireAuth({ children, adminOnly }: { children: ReactNode; adminOnly?: boolean }) {
  const { status, user } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <Loading />
  if (status === 'anonymous' || !user) {
    return <Navigate to={`/admin/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />
  }
  if (user.must_change_password && location.pathname !== '/admin/change-password') {
    return <Navigate to="/admin/change-password" replace />
  }
  if (adminOnly && user.role !== 'ADMIN') return <Navigate to="/admin" replace />
  return <>{children}</>
}

// ----------------------------------------------------------------- lookups

const LookupsContext = createContext<{ lookups: Lookups | null; reload: () => void }>({ lookups: null, reload: () => {} })

export function LookupsProvider({ children }: { children: ReactNode }) {
  const [lookups, setLookups] = useState<Lookups | null>(null)
  const [nonce, setNonce] = useState(0)
  const { status, user } = useAuth()
  useEffect(() => {
    if (status !== 'authenticated' || user?.must_change_password) return
    api
      .get<Lookups>('/lookups')
      .then(setLookups)
      .catch(() => setLookups(null))
  }, [status, user?.must_change_password, nonce])
  const value = useMemo(() => ({ lookups, reload: () => setNonce((n) => n + 1) }), [lookups])
  return <LookupsContext.Provider value={value}>{children}</LookupsContext.Provider>
}

export function useLookups() {
  return useContext(LookupsContext)
}
