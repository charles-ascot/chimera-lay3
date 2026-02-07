/**
 * CHIMERA v2 Toast Notifications
 */

import { useToastStore } from '../../store/toast'

export default function ToastContainer() {
  const { toasts, removeToast } = useToastStore()

  if (!toasts.length) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-md">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast toast-${toast.type} flex items-start gap-3 min-w-[300px]`}
        >
          <div className={`flex-shrink-0 mt-0.5 ${
            toast.type === 'success' ? 'text-chimera-success' :
            toast.type === 'error' ? 'text-chimera-error' :
            'text-chimera-cyan'
          }`}>
            {toast.type === 'success' && <SuccessIcon />}
            {toast.type === 'error' && <ErrorIcon />}
            {toast.type === 'info' && <InfoIcon />}
          </div>
          <p className="flex-1 text-sm text-white">{toast.message}</p>
          <button
            onClick={() => removeToast(toast.id)}
            className="flex-shrink-0 text-chimera-muted hover:text-white transition-colors"
          >
            <CloseIcon />
          </button>
        </div>
      ))}
    </div>
  )
}

function SuccessIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

function ErrorIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

function InfoIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}
