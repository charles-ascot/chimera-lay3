/**
 * CHIMERA v2 App Shell
 * Main layout wrapping navigation and content area
 */

import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'
import ToastContainer from '../shared/Toast'

export default function AppShell() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Top nav (desktop) */}
      <Navbar />

      {/* Main content area */}
      <main className="flex-1 px-4 md:px-6 py-4 pb-20 md:pb-6 overflow-y-auto">
        <Outlet />
      </main>

      {/* Toast notifications */}
      <ToastContainer />
    </div>
  )
}
