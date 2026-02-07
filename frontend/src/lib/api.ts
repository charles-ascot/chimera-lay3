/**
 * CHIMERA v2 REST API Client
 * Typed axios instance with interceptors for auth and error handling.
 */

import axios, { type AxiosInstance, type AxiosError } from 'axios'

const API_URL = import.meta.env.VITE_API_URL || ''

const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor — handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Session expired — trigger re-auth flow
      window.dispatchEvent(new CustomEvent('chimera:session-expired'))
    }
    return Promise.reject(error)
  }
)

// ─────────────────────────────────────────────────────────
// Auth
// ─────────────────────────────────────────────────────────

export const authApi = {
  login: (username: string, password: string) =>
    api.post('/api/auth/login', { username, password }),

  logout: () => api.post('/api/auth/logout'),

  keepAlive: () => api.post('/api/auth/keepalive'),

  getSession: () => api.get('/api/auth/session'),

  restoreSession: () => api.post('/api/auth/restore'),
}

// ─────────────────────────────────────────────────────────
// Markets
// ─────────────────────────────────────────────────────────

export const marketsApi = {
  getCatalogue: (params?: { max_results?: number; from_time?: string; to_time?: string }) =>
    api.get('/api/markets/catalogue', { params }),

  getBook: (marketIds: string[]) =>
    api.post('/api/markets/book', { market_ids: marketIds }),

  getSingleBook: (marketId: string) =>
    api.get(`/api/markets/${marketId}/book`),
}

// ─────────────────────────────────────────────────────────
// Orders
// ─────────────────────────────────────────────────────────

export const ordersApi = {
  place: (params: {
    market_id: string
    selection_id: number
    odds: number
    stake: number
    persistence_type?: string
  }) => api.post('/api/orders/place', params),

  cancel: (params: { market_id: string; bet_id?: string }) =>
    api.post('/api/orders/cancel', params),

  getCurrent: (marketIds?: string) =>
    api.get('/api/orders/current', { params: { market_ids: marketIds } }),
}

// ─────────────────────────────────────────────────────────
// Account
// ─────────────────────────────────────────────────────────

export const accountApi = {
  getBalance: () => api.get('/api/account/balance'),

  getStatement: (params?: { from_date?: string; to_date?: string; record_count?: number }) =>
    api.get('/api/account/statement', { params }),
}

// ─────────────────────────────────────────────────────────
// Auto Betting
// ─────────────────────────────────────────────────────────

export const autoApi = {
  start: (mode: string = 'STAGING') => api.post('/api/auto/start', null, { params: { mode } }),

  stop: () => api.post('/api/auto/stop'),

  goLive: () => api.post('/api/auto/go-live'),

  goStaging: () => api.post('/api/auto/go-staging'),

  getStatus: () => api.get('/api/auto/status'),

  getBets: (params?: { limit?: number; offset?: number; source?: string }) =>
    api.get('/api/auto/bets', { params }),

  updateSettings: (settings: Record<string, any>) =>
    api.put('/api/auto/settings', settings),

  getPlugins: () => api.get('/api/auto/plugins'),

  updatePlugin: (pluginId: string, update: Record<string, any>) =>
    api.put(`/api/auto/plugins/${pluginId}`, update),

  setPluginOrder: (pluginIds: string[]) =>
    api.put('/api/auto/plugins/order', { plugin_ids: pluginIds }),
}

// ─────────────────────────────────────────────────────────
// History
// ─────────────────────────────────────────────────────────

export const historyApi = {
  getBets: (params?: {
    period?: string
    date_from?: string
    date_to?: string
    source?: string
    status?: string
    limit?: number
    offset?: number
  }) => api.get('/api/history/bets', { params }),

  getStats: (params?: { period?: string; date_from?: string; date_to?: string }) =>
    api.get('/api/history/stats', { params }),

  exportCsv: (params?: { period?: string; date_from?: string; date_to?: string }) =>
    api.get('/api/history/export', { params, responseType: 'blob' }),

  getAnalysis: (params?: { period?: string; date_from?: string; date_to?: string }) =>
    api.get('/api/history/analysis', { params }),

  getAiAnalysis: (params: { period?: string; date_from?: string; date_to?: string; question?: string }) =>
    api.post('/api/history/ai-analysis', null, { params }),

  getDecisions: (params?: { market_id?: string; action?: string; limit?: number; offset?: number }) =>
    api.get('/api/history/decisions', { params }),
}

// ─────────────────────────────────────────────────────────
// Stream & Health
// ─────────────────────────────────────────────────────────

export const streamApi = {
  start: () => api.post('/api/stream/start'),
  stop: () => api.post('/api/stream/stop'),
  getStatus: () => api.get('/api/stream/status'),
  getCache: () => api.get('/api/stream/cache'),
}

export const healthApi = {
  check: () => api.get('/health'),
}

export default api
