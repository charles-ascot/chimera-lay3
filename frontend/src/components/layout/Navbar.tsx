/**
 * CHIMERA v2 Navigation Bar
 * Desktop: top horizontal | Mobile: bottom tab bar
 */

import { NavLink } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'
import { useAutoStore } from '../../store/auto'

const NAV_ITEMS = [
  { path: '/account', label: 'Account', icon: WalletIcon },
  { path: '/manual', label: 'Manual', icon: LayIcon },
  { path: '/auto', label: 'Auto', icon: BoltIcon },
  { path: '/history', label: 'History', icon: ChartIcon },
]

export default function Navbar() {
  const { logout } = useAuthStore()
  const status = useAutoStore((s) => s.status)
  const isEngineRunning = status?.is_running

  return (
    <>
      {/* Desktop Nav */}
      <nav className="hidden md:flex items-center justify-between px-6 py-3 glass-card rounded-none border-x-0 border-t-0">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-chimera-cyan to-chimera-purple flex items-center justify-center">
            <span className="text-white font-bold text-sm">C</span>
          </div>
          <span className="font-semibold text-chimera-text">CHIMERA</span>
          <span className="text-xs text-chimera-muted ml-1">v2</span>
        </div>

        <div className="flex items-center gap-1">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                isActive ? 'nav-tab-active' : 'nav-tab'
              }
            >
              <div className="flex items-center gap-2">
                <Icon className="w-4 h-4" />
                <span>{label}</span>
                {path === '/auto' && isEngineRunning && (
                  <span className="w-2 h-2 rounded-full bg-chimera-success animate-pulse" />
                )}
              </div>
            </NavLink>
          ))}
        </div>

        <button
          onClick={logout}
          className="text-sm text-chimera-muted hover:text-chimera-error transition-colors"
        >
          Logout
        </button>
      </nav>

      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 glass-card rounded-none border-x-0 border-b-0">
        <div className="flex items-center justify-around py-2 px-4">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 px-3 py-1 rounded-lg transition-colors ${
                  isActive
                    ? 'text-chimera-accent'
                    : 'text-chimera-muted hover:text-chimera-text'
                }`
              }
            >
              <div className="relative">
                <Icon className="w-5 h-5" />
                {path === '/auto' && isEngineRunning && (
                  <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-chimera-success animate-pulse" />
                )}
              </div>
              <span className="text-[10px] font-medium">{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </>
  )
}

// ── Icons ──

function WalletIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M21 12a2.25 2.25 0 0 0-2.25-2.25H15a3 3 0 1 1 0-6h.75A2.25 2.25 0 0 1 18 6v0a2.25 2.25 0 0 1-2.25 2.25H15M3 12h18M3 12a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 12m-18 0v6a2.25 2.25 0 0 0 2.25 2.25h13.5A2.25 2.25 0 0 0 21 18v-6" />
    </svg>
  )
}

function LayIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5" />
    </svg>
  )
}

function BoltIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round"
        d="m3.75 13.5 10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75Z" />
    </svg>
  )
}

function ChartIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
    </svg>
  )
}
