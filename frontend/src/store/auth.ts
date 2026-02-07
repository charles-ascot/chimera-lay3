/**
 * CHIMERA v2 Auth Store (Zustand)
 */

import { create } from 'zustand'
import { authApi } from '../lib/api'

interface AuthState {
  authenticated: boolean
  expiresAt: string | null
  loading: boolean
  error: string | null

  login: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
  restoreSession: () => Promise<boolean>
  keepAlive: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  authenticated: false,
  expiresAt: null,
  loading: false,
  error: null,

  login: async (username, password) => {
    set({ loading: true, error: null })
    try {
      const { data } = await authApi.login(username, password)
      set({
        authenticated: true,
        expiresAt: data.expires_at,
        loading: false,
      })
      return true
    } catch (err: any) {
      const message = err.response?.data?.detail || err.message || 'Login failed'
      set({ loading: false, error: message })
      return false
    }
  },

  logout: async () => {
    try {
      await authApi.logout()
    } catch {
      // Ignore errors — still clear local state
    }
    set({ authenticated: false, expiresAt: null })
  },

  restoreSession: async () => {
    set({ loading: true })
    try {
      const { data } = await authApi.restoreSession()
      if (data.authenticated) {
        set({ authenticated: true, expiresAt: data.expires_at, loading: false })
        return true
      }
      set({ loading: false })
      return false
    } catch {
      set({ loading: false })
      return false
    }
  },

  keepAlive: async () => {
    try {
      const { data } = await authApi.keepAlive()
      if (data.expires_at) {
        set({ expiresAt: data.expires_at })
      }
    } catch {
      set({ authenticated: false, expiresAt: null })
    }
  },

  clearError: () => set({ error: null }),
}))
