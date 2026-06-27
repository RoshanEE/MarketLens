import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { ResearchForm } from '../components/research/ResearchForm'
import { ProgressStream } from '../components/research/ProgressStream'
import { Card } from '../components/ui/Card'
import { researchApi } from '../services/api'
import { useSSE } from '../hooks/useSSE'
import type { CreateRunPayload } from '../types'

export function NewResearchPage() {
  const navigate = useNavigate()
  const [runId, setRunId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { events, isDone, error: sseError } = useSSE(runId)

  const handleSubmit = async (payload: CreateRunPayload) => {
    setSubmitting(true)
    try {
      const run = await researchApi.createRun(payload)
      setRunId(run.id)
    } finally {
      setSubmitting(false)
    }
  }

  // Navigate to the report once the pipeline completes
  if (isDone && runId) {
    const lastEvent = events[events.length - 1]
    if (lastEvent?.event === 'complete') {
      setTimeout(() => navigate(`/research/${runId}`), 1200)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/')} className="btn-secondary py-1.5">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">New Research Run</h1>
          <p className="text-sm text-slate-500">Enter competitors, topics, and source URLs to analyze</p>
        </div>
      </div>

      {!runId ? (
        <Card>
          <ResearchForm onSubmit={handleSubmit} loading={submitting} />
        </Card>
      ) : (
        <Card>
          <h2 className="mb-4 font-semibold text-slate-900">Pipeline Progress</h2>
          <ProgressStream events={events} isDone={isDone} />
          {sseError && <p className="mt-3 text-sm text-red-600">{sseError}</p>}
          {isDone && events.at(-1)?.event === 'complete' && (
            <p className="mt-3 text-sm text-emerald-600">Analysis complete! Redirecting to your report…</p>
          )}
          {isDone && events.at(-1)?.event === 'error' && (
            <button onClick={() => navigate('/')} className="btn-secondary mt-4">
              Back to dashboard
            </button>
          )}
        </Card>
      )}
    </div>
  )
}
