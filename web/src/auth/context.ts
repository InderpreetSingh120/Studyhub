import { createContext } from 'react'
import type { RegisterInput } from '../api/endpoints'
import type { User } from '../api/types'

export const STORAGE_KEY = 'studyhub.token'

export interface AuthContextValue {
  user: User | null
  /** 'loading' while the stored token is being validated. */
  status: 'loading' | 'ready'
  login: (identifier: string, password: string) => Promise<void>
  register: (input: RegisterInput) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
