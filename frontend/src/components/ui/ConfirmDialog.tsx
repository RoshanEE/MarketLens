import { useEffect } from 'react'
import { AlertTriangle, X } from 'lucide-react'

interface ConfirmDialogProps {
  title: string
  message: string
  confirmLabel?: string
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Confirm',
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onCancel])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" onClick={onCancel} />

      <div className="relative w-full max-w-sm rounded-2xl bg-white shadow-xl">
        <div className="flex items-start justify-between px-6 pt-5">
          <div className="flex items-start gap-3">
            {destructive && (
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-100">
                <AlertTriangle className="h-4 w-4 text-red-600" />
              </div>
            )}
            <div>
              <h2 className="font-semibold text-slate-900">{title}</h2>
              <p className="mt-1 text-sm text-slate-500">{message}</p>
            </div>
          </div>
          <button
            onClick={onCancel}
            className="ml-4 shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex justify-end gap-2 px-6 py-4">
          <button onClick={onCancel} className="btn-secondary text-sm">
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={destructive ? 'btn-danger text-sm' : 'btn-primary text-sm'}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
