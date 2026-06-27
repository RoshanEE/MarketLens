import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { PlusCircle, Clock, CheckCircle2, AlertCircle, Loader2, Trash2 } from 'lucide-react'
import { researchApi } from '../services/api'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { Card } from '../components/ui/Card'
import type { ResearchRunSummary, RunStatus } from '../types'

const statusConfig: Record<RunStatus, { label: string; variant: 'default' | 'success' | 'warning' | 'error' | 'info'; icon: React.ReactNode }> = {
  pending:   { label: 'Pending',   variant: 'default', icon: <Clock className="h-3.5 w-3.5" /> },
  crawling:  { label: 'Crawling',  variant: 'info',    icon: <Loader2 className="h-3.5 w-3.5 animate-spin" /> },
  analyzing: { label: 'Analyzing', variant: 'info',    icon: <Loader2 className="h-3.5 w-3.5 animate-spin" /> },
  judging:   { label: 'Verifying', variant: 'info',    icon: <Loader2 className="h-3.5 w-3.5 animate-spin" /> },
  complete:  { label: 'Complete',  variant: 'success', icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
  failed:    { label: 'Failed',    variant: 'error',   icon: <AlertCircle className="h-3.5 w-3.5" /> },
}

export function DashboardPage() {
  const [runs, setRuns] = useState<ResearchRunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    researchApi.listRuns().then(setRuns).finally(() => setLoading(false))
  }, [])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.preventDefault()
    if (!confirm('Delete this research run?')) return
    setDeletingId(id)
    await researchApi.deleteRun(id)
    setRuns((prev) => prev.filter((r) => r.id !== id))
    setDeletingId(null)
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Research Runs</h1>
          <p className="mt-1 text-sm text-slate-500">Your market intelligence history</p>
        </div>
        <Link to="/research/new" className="btn-primary">
          <PlusCircle className="h-4 w-4" /> New Research
        </Link>
      </div>

      {runs.length === 0 ? (
        <Card>
          <div className="py-12 text-center">
            <p className="text-slate-500">No research runs yet.</p>
            <Link to="/research/new" className="btn-primary mt-4 inline-flex">
              Start your first analysis
            </Link>
          </div>
        </Card>
      ) : (
        <div className="space-y-3">
          {runs.map((run) => {
            const { label, variant, icon } = statusConfig[run.status]
            return (
              <Link key={run.id} to={`/research/${run.id}`} className="block group">
                <Card className="transition-shadow hover:shadow-md">
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-slate-900 truncate group-hover:text-brand-700">
                          {run.title ?? 'Untitled Research'}
                        </h3>
                        <Badge variant={variant}>
                          <span className="flex items-center gap-1">{icon} {label}</span>
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-slate-500 truncate">
                        {[...run.competitors, ...run.topics].join(' · ') || 'No competitors or topics'}
                        {' · '}{run.url_count} URL{run.url_count !== 1 ? 's' : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <p className="text-xs text-slate-400">
                        {new Date(run.created_at).toLocaleDateString()}
                      </p>
                      <button
                        onClick={(e) => handleDelete(run.id, e)}
                        className="p-1 text-slate-300 hover:text-red-500 transition-colors"
                        disabled={deletingId === run.id}
                        title="Delete run"
                      >
                        {deletingId === run.id
                          ? <Spinner size="sm" />
                          : <Trash2 className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                </Card>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
