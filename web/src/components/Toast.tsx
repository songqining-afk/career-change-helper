import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'info'
}

interface ToastContextValue {
  toast: (message: string, type?: Toast['type']) => void
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  let nextId = 0

  const toast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = ++nextId
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3500)
  }, [])

  return (
    <ToastContext value={{ toast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-[100] space-y-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto px-4 py-3 rounded-xl text-sm font-medium shadow-lg animate-in fade-in slide-in-from-bottom-2 ${
              t.type === 'success'
                ? 'bg-success/90 text-white'
                : t.type === 'error'
                ? 'bg-danger/90 text-white'
                : 'bg-surface-2 text-text-primary border border-border'
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext>
  )
}
