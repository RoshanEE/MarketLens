import { useEffect } from 'react'
import { X } from 'lucide-react'
import { ResearchForm } from '../research/ResearchForm'
import type { CreateRunPayload, ResearchRun } from '../../types'

interface RerunModalProps {
  run: ResearchRun
  submitting: boolean
  onSubmit: (payload: CreateRunPayload) => Promise<void>
  onClose: () => void
}

export function RerunModal({ run, submitting, onSubmit, onClose }: RerunModalProps) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Dialog */}
      <div className="relative w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white shadow-xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white px-6 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">Run Again</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Edit the configuration below before re-running.
              {run.title && <> · <span className="italic">{run.title}</span></>}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 py-5">
          <ResearchForm
            onSubmit={(payload) => onSubmit({ ...payload, title: run.title ?? undefined, source_run_id: run.id })}
            loading={submitting}
            hideTitle
            submitLabel="Run Again"
            initialValues={{
              competitors: run.competitors,
              topics: run.topics,
              urls: run.source_urls.map(s => s.url),
              context: run.context ?? undefined,
            }}
          />
        </div>
      </div>
    </div>
  )
}
