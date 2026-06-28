import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  PlusCircle, ChevronDown, ChevronUp, RefreshCw,
  BarChart3, CheckCircle2, Loader2, AlertCircle,
} from 'lucide-react'
import { clsx } from 'clsx'
import { researchApi } from '../services/api'
import { RunsTable } from '../components/dashboard/RunsTable'
import { Spinner } from '../components/ui/Spinner'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import type { ResearchRunSummary } from '../types'

// ── Stat card ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  value: number
  label: string
  colorClass: string
  activeClass: string
  Icon: React.ComponentType<{ className?: string }>
  filterValue: string
  activeFilter: string
  onFilterChange: (v: string) => void
}

function StatCard({ value, label, colorClass, activeClass, Icon, filterValue, activeFilter, onFilterChange }: StatCardProps) {
  const isActive = activeFilter === filterValue && filterValue !== 'All'
  return (
    <button
      onClick={() => onFilterChange(isActive ? 'All' : filterValue)}
      className={clsx(
        'rounded-xl border p-4 w-full text-left transition-all',
        colorClass,
        isActive ? activeClass : 'hover:shadow-md',
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-2xl font-bold">{value}</p>
          <p className="mt-0.5 text-xs font-medium opacity-75">{label}</p>
        </div>
        <Icon className="h-7 w-7 opacity-20" />
      </div>
      {isActive && (
        <p className="mt-2 text-xs font-medium opacity-60">Filtering table ↓  click to clear</p>
      )}
    </button>
  )
}

// ── Refresh button ─────────────────────────────────────────────────────────────

function RefreshButton({ onClick, spinning }: { onClick: () => void; spinning: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={spinning}
      className="rounded-md p-1 text-slate-400 hover:text-brand-600 hover:bg-brand-50 transition-colors disabled:opacity-40"
      title="Refresh"
    >
      <RefreshCw className={clsx('h-3.5 w-3.5', spinning && 'animate-spin')} />
    </button>
  )
}

// ── Collapsible section ────────────────────────────────────────────────────────

interface CollapsibleSectionProps {
  title: string
  badge?: number
  defaultOpen?: boolean
  action?: React.ReactNode
  children: React.ReactNode
}

function CollapsibleSection({ title, badge, defaultOpen = true, action, children }: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5">
        <button
          onClick={() => setOpen(o => !o)}
          className="flex flex-1 items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <span className="text-sm font-semibold text-slate-900">{title}</span>
          {badge !== undefined && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
              {badge}
            </span>
          )}
          {open
            ? <ChevronUp className="ml-1 h-4 w-4 text-slate-400" />
            : <ChevronDown className="ml-1 h-4 w-4 text-slate-400" />}
        </button>
        {action}
      </div>
      {open && <div className="border-t border-slate-100 px-5 py-4">{children}</div>}
    </div>
  )
}

// ── Mini card (recent panel) ───────────────────────────────────────────────────

function RunMiniCard({ run }: { run: ResearchRunSummary }) {
  const tags = [...run.competitors, ...run.topics]
  return (
    <Link
      to={`/research/${run.id}`}
      className="block rounded-lg border border-slate-200 p-3 hover:border-brand-500 hover:shadow-sm transition-all group"
    >
      <p className="truncate text-sm font-medium text-slate-900 group-hover:text-brand-600">
        {run.title ?? 'Untitled Research'}
      </p>
      {tags.length > 0 && (
        <p className="mt-0.5 truncate text-xs text-slate-400">{tags.join(' · ')}</p>
      )}
      <p className="mt-1.5 text-xs text-slate-400">{new Date(run.created_at).toLocaleDateString()}</p>
    </Link>
  )
}

// ── Dashboard ──────────────────────────────────────────────────────────────────

export function DashboardPage() {
  const [runs, setRuns] = useState<ResearchRunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [statusFilter, setStatusFilter] = useState('All')

  useEffect(() => {
    researchApi.listRuns().then(setRuns).finally(() => setLoading(false))
  }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    try { setRuns(await researchApi.listRuns()) }
    finally { setRefreshing(false) }
  }

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDeleteConfirmId(id)
  }

  const confirmDelete = async () => {
    const id = deleteConfirmId
    if (!id) return
    setDeleteConfirmId(null)
    setDeletingId(id)
    await researchApi.deleteRun(id)
    setRuns(prev => prev.filter(r => r.id !== id))
    setDeletingId(null)
  }

  const stats = useMemo(() => ({
    total:      runs.length,
    complete:   runs.filter(r => r.status === 'complete').length,
    inProgress: runs.filter(r => ['pending', 'crawling', 'analyzing', 'judging'].includes(r.status)).length,
    failed:     runs.filter(r => r.status === 'failed').length,
  }), [runs])

  const recentRuns = useMemo(() => runs.filter(r => r.status === 'complete').slice(0, 3), [runs])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">Your market intelligence workspace</p>
        </div>
        <Link to="/research/new" className="btn-primary">
          <PlusCircle className="h-4 w-4" /> New Research
        </Link>
      </div>

      {/* ── Stats strip ─────────────────────────────────────────────── */}
      {runs.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            value={stats.total} label="Total Runs"
            colorClass="border-slate-200 bg-white text-slate-800"
            activeClass="ring-2 ring-slate-400 ring-offset-1"
            Icon={BarChart3} filterValue="All"
            activeFilter={statusFilter} onFilterChange={setStatusFilter}
          />
          <StatCard
            value={stats.complete} label="Complete"
            colorClass="border-emerald-100 bg-emerald-50 text-emerald-800"
            activeClass="ring-2 ring-emerald-500 ring-offset-1"
            Icon={CheckCircle2} filterValue="Complete"
            activeFilter={statusFilter} onFilterChange={setStatusFilter}
          />
          <StatCard
            value={stats.inProgress} label="In Progress"
            colorClass="border-brand-100 bg-brand-50 text-brand-800"
            activeClass="ring-2 ring-brand-500 ring-offset-1"
            Icon={Loader2} filterValue="In Progress"
            activeFilter={statusFilter} onFilterChange={setStatusFilter}
          />
          <StatCard
            value={stats.failed} label="Failed"
            colorClass="border-red-100 bg-red-50 text-red-800"
            activeClass="ring-2 ring-red-500 ring-offset-1"
            Icon={AlertCircle} filterValue="Failed"
            activeFilter={statusFilter} onFilterChange={setStatusFilter}
          />
        </div>
      )}

      {/* ── Recent completed ────────────────────────────────────────── */}
      {recentRuns.length > 0 && (
        <CollapsibleSection
          title="Recent Reports"
          badge={recentRuns.length}
          action={<RefreshButton onClick={handleRefresh} spinning={refreshing} />}
        >
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {recentRuns.map(run => <RunMiniCard key={run.id} run={run} />)}
          </div>
        </CollapsibleSection>
      )}

      {/* ── All runs table ───────────────────────────────────────────── */}
      <div className="card p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-900">All Runs</h2>
            <RefreshButton onClick={handleRefresh} spinning={refreshing} />
          </div>
          {runs.length === 0 && (
            <Link to="/research/new" className="btn-primary">Start your first analysis</Link>
          )}
        </div>
        <RunsTable
          runs={runs}
          onDelete={handleDelete}
          deletingId={deletingId}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
        />
      </div>

      {deleteConfirmId && (
        <ConfirmDialog
          title="Delete research run?"
          message="This will permanently remove the run and its report. This action cannot be undone."
          confirmLabel="Delete"
          destructive
          onConfirm={confirmDelete}
          onCancel={() => setDeleteConfirmId(null)}
        />
      )}
    </div>
  )
}
