/**
 * CHIMERA v2 Toast Store (Zustand)
 */

import { create } from 'zustand'
import { uid } from '../lib/utils'
import type { ToastMessage } from '../types/app'

interface ToastState {
  toasts: ToastMessage[]
  addToast: (message: string, type?: 'success' | 'error' | 'info') => void
  removeToast: (id: string) => void
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (message, type = 'info') => {
    const id = uid()
    set((state) => ({
      toasts: [...state.toasts, { id, message, type }],
    }))

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }))
    }, 5000)
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }))
  },
}))
