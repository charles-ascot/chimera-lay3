/**
 * CHIMERA v2 App
 * Router + auth guard + WebSocket connection + keepAlive timer
 */

import { useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

import { useAuthStore } from './store/auth'
import { useMarketsStore } from './store/markets'
import { useAutoStore } from './store/auto'
import { useToastStore } from './store/toast'
import chimeraWS from './lib/ws'

import AppShell from './components/layout/AppShell'
import LoadingSpinner from './components/shared/LoadingSpinner'

// Pages (lazy-loaded later, inline for now)
import LoginPage from './pages/LoginPage'
import AccountPage from './pages/AccountPage'
import ManualBettingPage from './pages/ManualBettingPage'
import AutoBettingPage from './pages/AutoBettingPage'
import HistoryPage from './pages/HistoryPage'

export default function App() {
  const { authenticated, loading, restoreSession, keepAlive } = useAuthStore()
  const { updatePrices, updateMarketStatus } = useMarketsStore()
  const { addActivity, updateEngineStatus } = useAutoStore()
  const { addToast } = useToastStore()
  const keepAliveRef = useRef<ReturnType<typeof setInterval>>()
  const restored = useRef(false)

  // Restore session on mount
  useEffect(() => {
    if (!restored.current) {
      restored.current = true
      restoreSession()
    }
  }, [restoreSession])

  // KeepAlive timer (every 20 min)
  useEffect(() => {
    if (authenticated) {
      keepAliveRef.current = setInterval(keepAlive, 20 * 60 * 1000)
      return () => clearInterval(keepAliveRef.current)
    }
  }, [authenticated, keepAlive])

  // WebSocket connection
  useEffect(() => {
    if (authenticated) {
      chimeraWS.setHandlers({
        onPriceUpdate: (data) => {
          updatePrices(data.marketId, data.runners)
        },
        onMarketStatus: (data) => {
          updateMarketStatus(data.marketId, data.status, data.inPlay)
        },
        onOrderUpdate: (data) => {
          addToast(
            `Order ${data.betId}: ${data.status} (${data.sizeMatched} matched)`,
            'info'
          )
        },
        onEngineStatus: (data) => {
          updateEngineStatus(data)
        },
        onEngineActivity: (data) => {
          addActivity(data)
          if (data.type === 'bet_placed') {
            addToast(
              `Auto bet: ${data.runner_name} @ ${data.odds} (${data.zone})`,
              'success'
            )
          } else if (data.type === 'bet_failed') {
            addToast(`Auto bet failed: ${data.reason}`, 'error')
          }
        },
        onConnected: () => {
          console.log('WebSocket connected')
        },
        onDisconnected: () => {
          console.log('WebSocket disconnected')
        },
      })
      chimeraWS.connect()

      return () => chimeraWS.disconnect()
    }
  }, [authenticated])

  // Listen for session expiry
  useEffect(() => {
    const handler = () => {
      addToast('Session expired. Please log in again.', 'error')
      useAuthStore.getState().logout()
    }
    window.addEventListener('chimera:session-expired', handler)
    return () => window.removeEventListener('chimera:session-expired', handler)
  }, [addToast])

  // Loading state
  if (loading && !authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <LoadingSpinner size="lg" className="mb-4" />
          <p className="text-chimera-muted">Restoring session...</p>
        </div>
      </div>
    )
  }

  // Not authenticated
  if (!authenticated) {
    return <LoginPage />
  }

  // Authenticated — show app
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/account" element={<AccountPage />} />
          <Route path="/manual" element={<ManualBettingPage />} />
          <Route path="/auto" element={<AutoBettingPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="*" element={<Navigate to="/account" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
