import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { researchApi } from '../services/api'
import { ReportView } from '../components/reports/ReportView'
import { ProgressStream } from '../components/research/ProgressStream'
import { Spinner } from '../components/ui/Spinner'
import { Card } from '../components/ui/Card'
import { useSSE } from '../hooks/useSSE'
import type { ResearchRun } from '../types'

export function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [run, setRun] = useState<ResearchRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // SSE is only active for in-progress runs
  const inProgress = run && !['complete', 'failed'].includes(run.status)
  const { events, isDone } = useSSE(inProgress && id ? id : null)

  // Reload run data when pipeline finishes
  useEffect(() => {
    if (isDone && id) {
      researchApi.getRun(id).then(setRun)
    }
  }, [isDone, id])

  useEffect(() => {
    if (!id) return
    researchApi
      .getRun(id)
      .then(setRun)
      .catch(() => setError('Run not found.'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error || !run) {
    return (
      <div className="text-center py-16">
        <p className="text-slate-500">{error ?? 'Run not found.'}</p>
        <Link to="/" className="btn-primary mt-4 inline-flex">Back to dashboard</Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/')} className="btn-secondary py-1.5">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <h1 className="text-xl font-bold text-slate-900 truncate">{run.title ?? 'Research Report'}</h1>
      </div>

      {/* In-progress view */}
      {inProgress && (
        <Card>
          <h2 className="mb-4 font-semibold text-slate-900">Pipeline Progress</h2>
          <ProgressStream events={events} isDone={isDone} />
        </Card>
      )}

      {/* Failed view */}
      {run.status === 'failed' && (
        <Card>
          <div className="flex items-start gap-3 text-red-600">
            <RefreshCw className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Pipeline failed</p>
              {run.error && <p className="text-sm mt-1">{run.error}</p>}
            </div>
          </div>
        </Card>
      )}

      {/* Completed report */}
      {run.status === 'complete' && run.report && (
        <ReportView run={run} report={run.report} />
      )}
    </div>
  )
}
