/**
 * CHIMERA v2 Login Page
 * Betfair credentials login with glass card styling
 */

import { useState } from 'react'
import { useAuthStore } from '../store/auth'
import LoadingSpinner from '../components/shared/LoadingSpinner'

export default function LoginPage() {
  const { login, loading, error, clearError } = useAuthStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username || !password) return
    await login(username, password)
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-chimera-cyan to-chimera-purple flex items-center justify-center shadow-lg">
            <span className="text-3xl font-bold text-white">C</span>
          </div>
          <h1 className="text-2xl font-bold text-chimera-text">CHIMERA</h1>
          <p className="text-chimera-muted text-sm mt-1">Lay Betting Engine v2</p>
        </div>

        {/* Login Card */}
        <form onSubmit={handleSubmit} className="glass-card p-8 rounded-2xl space-y-6">
          <div>
            <label className="block text-sm font-medium text-chimera-text-secondary mb-2">
              Betfair Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => { setUsername(e.target.value); clearError() }}
              className="input-field"
              placeholder="Enter username"
              autoComplete="username"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-chimera-text-secondary mb-2">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); clearError() }}
              className="input-field"
              placeholder="Enter password"
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-chimera-error/10 border border-chimera-error/20">
              <p className="text-sm text-chimera-error">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username || !password}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <LoadingSpinner size="sm" />
                <span>Connecting...</span>
              </>
            ) : (
              'Login to Betfair'
            )}
          </button>
        </form>

        <p className="text-center text-xs text-chimera-muted mt-6">
          GB & IE Horse Racing | WIN Markets Only
        </p>
      </div>
    </div>
  )
}
