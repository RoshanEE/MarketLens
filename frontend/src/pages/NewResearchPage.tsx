import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, StopCircle, Loader2 } from 'lucide-react'
import { ResearchForm } from '../components/research/ResearchForm'
import { PipelineProgress } from '../components/research/PipelineProgress'
import { Card } from '../components/ui/Card'
import { researchApi } from '../services/api'
import { useSSE } from '../hooks/useSSE'
import type { CreateRunPayload } from '../types'

export function NewResearchPage() {
  const navigate = useNavigate()
  const [runId, setRunId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [cancelState, setCancelState] = useState<'idle' | 'stopping' | 'stopped'>('idle')
  const [lastPayload, setLastPayload] = useState<CreateRunPayload | null>(null)

  const { events, isDone, error: sseError } = useSSE(runId)

  const handleSubmit = async (payload: CreateRunPayload) => {
    setSubmitting(true)
    setLastPayload(payload)
    try {
      const run = await researchApi.createRun(payload)
      setRunId(run.id)
    } finally {
      setSubmitting(false)
    }
  }

  const handleRetry = () => {
    if (lastPayload) handleSubmit(lastPayload)
  }

  const handleCancel = async () => {
    if (!runId) return
    setCancelState('stopping')
    await researchApi.cancelRun(runId)
    setCancelState('stopped')
    navigate(`/research/${runId}`)
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
          <h2 className="mb-6 font-semibold text-slate-900">Pipeline Progress</h2>
          <PipelineProgress
            events={events}
            isDone={isDone}
            onViewReport={() => navigate(`/research/${runId}`)}
            onRetry={handleRetry}
          />
          {!isDone && (
            <div className="mt-4 flex justify-end">
              <button onClick={handleCancel} disabled={cancelState !== 'idle'} className="btn-danger text-xs py-1.5">
                {cancelState === 'stopping' && <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Stopping…</>}
                {cancelState === 'stopped'  && <>Stopped</>}
                {cancelState === 'idle'     && <><StopCircle className="h-3.5 w-3.5" /> Stop pipeline</>}
              </button>
            </div>
          )}
          {sseError && (
            <p className="mt-4 text-sm text-red-600">{sseError}</p>
          )}
        </Card>
      )}
    </div>
  )
}
