/**
 * CHIMERA v2 Auto-Betting Store (Zustand)
 * Engine status and control from frontend
 */

import { create } from 'zustand'
import { autoApi } from '../lib/api'
import type { AutoBettingStatus, Bet } from '../types/app'
import type { Plugin } from '../types/plugin'

interface AutoState {
  status: AutoBettingStatus | null
  plugins: Plugin[]
  autoBets: Bet[]
  activityLog: Array<{ type: string; data: any; timestamp: string }>
  loading: boolean
  error: string | null

  fetchStatus: () => Promise<void>
  fetchPlugins: () => Promise<void>
  fetchAutoBets: () => Promise<void>
  startEngine: () => Promise<boolean>
  stopEngine: () => Promise<boolean>
  togglePlugin: (pluginId: string, enabled: boolean) => Promise<void>
  updateSettings: (settings: Record<string, any>) => Promise<void>
  addActivity: (activity: any) => void
  updateEngineStatus: (data: any) => void
}

export const useAutoStore = create<AutoState>((set, get) => ({
  status: null,
  plugins: [],
  autoBets: [],
  activityLog: [],
  loading: false,
  error: null,

  fetchStatus: async () => {
    try {
      const { data } = await autoApi.getStatus()
      set({ status: data })
    } catch (err: any) {
      set({ error: err.response?.data?.detail || 'Failed to fetch status' })
    }
  },

  fetchPlugins: async () => {
    try {
      const { data } = await autoApi.getPlugins()
      set({ plugins: data.plugins || [] })
    } catch (err: any) {
      set({ error: err.response?.data?.detail || 'Failed to fetch plugins' })
    }
  },

  fetchAutoBets: async () => {
    try {
      const { data } = await autoApi.getBets({ limit: 50 })
      set({ autoBets: data.bets || [] })
    } catch {
      // Ignore
    }
  },

  startEngine: async () => {
    set({ loading: true })
    try {
      await autoApi.start()
      await get().fetchStatus()
      set({ loading: false })
      return true
    } catch (err: any) {
      set({ loading: false, error: err.response?.data?.detail || 'Failed to start' })
      return false
    }
  },

  stopEngine: async () => {
    set({ loading: true })
    try {
      await autoApi.stop()
      await get().fetchStatus()
      set({ loading: false })
      return true
    } catch (err: any) {
      set({ loading: false, error: err.response?.data?.detail || 'Failed to stop' })
      return false
    }
  },

  togglePlugin: async (pluginId, enabled) => {
    try {
      await autoApi.updatePlugin(pluginId, { enabled })
      await get().fetchPlugins()
    } catch {
      // Ignore
    }
  },

  updateSettings: async (settings) => {
    try {
      await autoApi.updateSettings(settings)
      await get().fetchStatus()
    } catch {
      // Ignore
    }
  },

  addActivity: (activity) => {
    set((state) => ({
      activityLog: [
        { ...activity, timestamp: new Date().toISOString() },
        ...state.activityLog.slice(0, 99), // Keep last 100
      ],
    }))
  },

  updateEngineStatus: (data) => {
    set((state) => ({
      status: state.status ? { ...state.status, ...data } : null,
    }))
  },
}))
