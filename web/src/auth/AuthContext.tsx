import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { auth } from '../api/endpoints'
import { setAuthToken } from '../api/http'
import type { User } from '../api/types'
import { AuthContext, STORAGE_KEY, type AuthContextValue } from './context'

function storeToken(token: string | null): void {
  if (token) localStorage.setItem(STORAGE_KEY, token)
  else localStorage.removeItem(STORAGE_KEY)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready'>(() =>
    localStorage.getItem(STORAGE_KEY) ? 'loading' : 'ready',
  )

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return
    setAuthToken(stored)
    auth
      .me()
      .then(setUser)
      .catch(() => {
        setAuthToken(null)
        storeToken(null)
      })
      .finally(() => setStatus('ready'))
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      async login(identifier, password) {
        const response = await auth.login({ identifier, password })
        storeToken(response.access_token)
        setAuthToken(response.access_token)
        setUser(response.user)
      },
      async register(input) {
        const response = await auth.register(input)
        storeToken(response.access_token)
        setAuthToken(response.access_token)
        setUser(response.user)
      },
      logout() {
        storeToken(null)
        setAuthToken(null)
        setUser(null)
      },
    }),
    [user, status],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
