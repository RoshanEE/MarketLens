import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, AlertCircle, Loader2 } from 'lucide-react'
import { researchApi } from '../services/api'
import { ReportView } from '../components/reports/ReportView'
import { PipelineProgress } from '../components/research/PipelineProgress'
import { Spinner } from '../components/ui/Spinner'
import { Card } from '../components/ui/Card'
import { useSSE } from '../hooks/useSSE'
import type { ResearchRun, CreateRunPayload } from '../types'

const ACTIVE_STATUSES = ['crawling', 'analyzing', 'judging']
const POLL_INTERVAL_MS = 3000

export function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [run, setRun] = useState<ResearchRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Controls whether the report section is visible.
  // True immediately if the run was already complete/failed when the page loaded.
  // Otherwise the user must click "View Report" after the pipeline finishes.
  const [showReport, setShowReport] = useState(false)

  // Only connect to SSE (and trigger pipeline) when run is in 'pending' state.
  const [streamingRunId, setStreamingRunId] = useState<string | null>(null)
  const { events, isDone } = useSSE(streamingRunId)
  const streamStartedRef = useRef<string | null>(null)

  // Load run on mount / id change
  useEffect(() => {
    if (!id) return
    setRun(null)
    setLoading(true)
    setError(null)
    setShowReport(false)
    setStreamingRunId(null)
    streamStartedRef.current = null
    researchApi.getRun(id)
      .then(fetched => {
        setRun(fetched)
        // Already finished — show report immediately without making them click
        if (fetched.status === 'complete' || fetched.status === 'failed') {
          setShowReport(true)
        }
      })
      .catch(() => setError('Run not found.'))
      .finally(() => setLoading(false))
  }, [id])

  // Start SSE only for pending runs (triggers pipeline on backend)
  useEffect(() => {
    if (!run || !id) return
    if (run.status === 'pending' && streamStartedRef.current !== id) {
      streamStartedRef.current = id
      setStreamingRunId(id)
    }
  }, [run?.status, id])

  // When SSE stream ends, reload run but do NOT auto-show report —
  // user clicks "View Report" in PipelineProgress instead.
  useEffect(() => {
    if (isDone && id) {
      setStreamingRunId(null)
      streamStartedRef.current = null
      researchApi.getRun(id).then(setRun)
    }
  }, [isDone, id])

  // Poll for completion when pipeline is running but we're not connected via SSE
  const isPolling = run && ACTIVE_STATUSES.includes(run.status) && !streamingRunId
  useEffect(() => {
    if (!isPolling || !id) return
    const timer = setInterval(async () => {
      try {
        const updated = await researchApi.getRun(id)
        setRun(updated)
        if (['complete', 'failed'].includes(updated.status)) {
          clearInterval(timer)
        }
      } catch {
        // ignore transient errors — keep polling
      }
    }, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [isPolling, id])

  const handleRerun = async (payload: CreateRunPayload) => {
    const newRun = await researchApi.createRun(payload)
    navigate(`/research/${newRun.id}`)
  }

  const handleTitleChange = async (title: string) => {
    if (!id) return
    const updated = await researchApi.patchRun(id, { title })
    setRun(updated)
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error || !run) {
    return (
      <div className="py-16 text-center">
        <p className="text-slate-500">{error ?? 'Run not found.'}</p>
        <Link to="/" className="btn-primary mt-4 inline-flex">Back to dashboard</Link>
      </div>
    )
  }

  const showSSEProgress = !!streamingRunId || (isDone && !showReport)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 print:hidden">
        <button onClick={() => navigate('/')} className="btn-secondary py-1.5">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <h1 className="text-xl font-bold text-slate-900 truncate">{run.title ?? 'Research Report'}</h1>
      </div>

      {/* SSE-driven pipeline progress (new run or rerun) */}
      {showSSEProgress && (
        <Card>
          <h2 className="mb-6 font-semibold text-slate-900">Pipeline Progress</h2>
          <PipelineProgress
            events={events}
            isDone={isDone}
            onViewReport={() => {
              researchApi.getRun(id!).then(setRun)
              setShowReport(true)
            }}
          />
        </Card>
      )}

      {/* Polling view — pipeline already running when page loaded */}
      {isPolling && (
        <Card>
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-brand-500 shrink-0" />
            <div>
              <p className="font-medium text-slate-900">Pipeline is running</p>
              <p className="text-sm text-slate-500 capitalize">
                Status: {run.status} · checking for updates every {POLL_INTERVAL_MS / 1000}s…
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Failed view */}
      {run.status === 'failed' && showReport && (
        <Card>
          <div className="flex items-start gap-3 text-red-600">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Pipeline failed</p>
              {run.error && <p className="mt-1 text-sm">{run.error}</p>}
            </div>
          </div>
          <button
            onClick={() => run && handleRerun({
              title: run.title ?? undefined,
              competitors: run.competitors,
              topics: run.topics,
              urls: run.source_urls.map(s => s.url),
              context: run.context ?? undefined,
            })}
            className="btn-secondary mt-4 text-sm print:hidden"
          >
            <ArrowLeft className="h-4 w-4" /> Try again with same URLs
          </button>
        </Card>
      )}

      {/* Completed report */}
      {run.status === 'complete' && run.report && showReport && (
        <ReportView
          run={run}
          report={run.report}
          onRerun={handleRerun}
          onTitleChange={handleTitleChange}
        />
      )}
    </div>
  )
}
