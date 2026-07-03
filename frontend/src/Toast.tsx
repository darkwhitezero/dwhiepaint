import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'

type ToastKind = 'success' | 'error'
interface ToastItem {
  id: number
  kind: ToastKind
  text: string
}
interface ToastApi {
  success: (text: string) => void
  error: (text: string) => void
}

const ToastCtx = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const idRef = useRef(0)

  const push = useCallback((kind: ToastKind, text: string) => {
    const id = ++idRef.current
    setItems((list) => [...list, { id, kind, text }])
    // Auto-dismiss (Forms & Feedback: toasts 3–5s).
    window.setTimeout(() => setItems((list) => list.filter((t) => t.id !== id)), 4000)
  }, [])

  const api = useMemo<ToastApi>(
    () => ({
      success: (text) => push('success', text),
      error: (text) => push('error', text),
    }),
    [push],
  )

  return (
    <ToastCtx.Provider value={api}>
      {children}
      {/* Non-blocking, announced politely so it never steals focus. */}
      <div className="toast-stack" aria-live="polite" aria-atomic="false">
        {items.map((t) => (
          <div key={t.id} className={`toast toast--${t.kind}`} role="status">
            <span className="toast-icon" aria-hidden="true">
              {t.kind === 'success' ? '✓' : '!'}
            </span>
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastCtx)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}
