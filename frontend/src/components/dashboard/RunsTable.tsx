import { useState, useMemo, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'
import { CheckCircle2, AlertCircle, Loader2, Clock } from 'lucide-react'
import type { ResearchRunSummary, RunStatus } from '../../types'

const STATUS_CONFIG: Record<RunStatus, { label: string; variant: 'default' | 'success' | 'warning' | 'error' | 'info'; icon: React.ReactNode }> = {
  pending:   { label: 'Pending',   variant: 'default', icon: <Clock className="h-3 w-3" /> },
  crawling:  { label: 'Crawling',  variant: 'info',    icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  analyzing: { label: 'Analyzing', variant: 'info',    icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  judging:   { label: 'Verifying', variant: 'info',    icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  complete:  { label: 'Complete',  variant: 'success', icon: <CheckCircle2 className="h-3 w-3" /> },
  failed:    { label: 'Failed',    variant: 'error',   icon: <AlertCircle className="h-3 w-3" /> },
}

const STATUS_FILTER_OPTIONS: { label: string; statuses: RunStatus[] }[] = [
  { label: 'All',         statuses: [] },
  { label: 'Complete',    statuses: ['complete'] },
  { label: 'In Progress', statuses: ['pending', 'crawling', 'analyzing', 'judging'] },
  { label: 'Failed',      statuses: ['failed'] },
]

const PAGE_SIZES = [10, 25, 50]

interface RunsTableProps {
  runs: ResearchRunSummary[]
  onDelete: (id: string, e: React.MouseEvent) => void
  deletingId: string | null
  statusFilter: string
  onStatusFilterChange: (v: string) => void
}

export function RunsTable({ runs, onDelete, deletingId, statusFilter, onStatusFilterChange }: RunsTableProps) {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  // Reset to page 1 whenever search or filter changes
  useEffect(() => setPage(1), [search, statusFilter])

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim()
    const allowed = STATUS_FILTER_OPTIONS.find(o => o.label === statusFilter)?.statuses ?? []
    return runs.filter(run => {
      const matchSearch =
        !q ||
        run.title?.toLowerCase().includes(q) ||
        run.competitors.some(c => c.toLowerCase().includes(q)) ||
        run.topics.some(t => t.toLowerCase().includes(q))
      const matchStatus = allowed.length === 0 || allowed.includes(run.status)
      return matchSearch && matchStatus
    })
  }, [runs, search, statusFilter])

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize)
  const rangeStart = filtered.length === 0 ? 0 : (page - 1) * pageSize + 1
  const rangeEnd = Math.min(page * pageSize, filtered.length)

  return (
    <div className="space-y-3">
      {/* Search + filter bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search by title, competitor, or topic…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input pl-9"
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => onStatusFilterChange(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700
                     focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          {STATUS_FILTER_OPTIONS.map(o => (
            <option key={o.label} value={o.label}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <p className="py-10 text-center text-sm text-slate-400">
          {search || statusFilter !== 'All' ? 'No runs match your filters.' : 'No research runs yet.'}
        </p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left">
                  <th className="px-4 py-3 font-medium text-slate-500">Title</th>
                  <th className="px-4 py-3 font-medium text-slate-500">Status</th>
                  <th className="px-4 py-3 font-medium text-slate-500 hidden lg:table-cell">Results</th>
                  <th className="px-4 py-3 font-medium text-slate-500 hidden sm:table-cell">URLs</th>
                  <th className="px-4 py-3 font-medium text-slate-500 hidden md:table-cell">Date</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {paginated.map(run => {
                  const { label, variant, icon } = STATUS_CONFIG[run.status]
                  const tags = [...run.competitors, ...run.topics]
                  return (
                    <tr
                      key={run.id}
                      onClick={() => navigate(`/research/${run.id}`)}
                      className="cursor-pointer hover:bg-slate-50 transition-colors"
                    >
                      <td className="px-4 py-3 max-w-xs">
                        <p className="font-medium text-slate-900 truncate">{run.title ?? 'Untitled Research'}</p>
                        {tags.length > 0 && (
                          <p className="text-xs text-slate-400 truncate mt-0.5">{tags.join(' · ')}</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={variant}>
                          <span className="flex items-center gap-1">{icon} {label}</span>
                        </Badge>
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell">
                        {run.status === 'complete' && run.overall_confidence !== null ? (() => {
                          const pct = run.overall_confidence ?? 0
                          const confColor = pct >= 0.75
                            ? 'text-emerald-600'
                            : pct >= 0.5
                            ? 'text-amber-500'
                            : 'text-red-500'
                          return (
                            <div className="space-y-0.5">
                              <p className={`text-sm font-medium ${confColor}`}>
                                {(pct * 100).toFixed(0)}% confidence
                              </p>
                              {run.verified_claims !== null && run.total_claims !== null && (
                                <p className="text-xs text-slate-400">
                                  {run.verified_claims}/{run.total_claims} claims verified
                                </p>
                              )}
                            </div>
                          )
                        })() : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-500 hidden sm:table-cell">{run.url_count}</td>
                      <td className="px-4 py-3 text-slate-400 whitespace-nowrap hidden md:table-cell">
                        {new Date(run.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end" onClick={e => e.stopPropagation()}>
                          <button
                            onClick={e => onDelete(run.id, e)}
                            disabled={deletingId === run.id}
                            className="p-1.5 rounded-md text-slate-300 hover:text-red-500 transition-colors disabled:opacity-50"
                            title="Delete"
                          >
                            {deletingId === run.id ? <Spinner size="sm" /> : <Trash2 className="h-4 w-4" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination bar */}
          <div className="flex items-center justify-between text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <span>Rows per page</span>
              <select
                value={pageSize}
                onChange={e => { setPageSize(Number(e.target.value)); setPage(1) }}
                className="rounded border border-slate-200 bg-white px-1.5 py-1 text-xs
                           focus:border-brand-500 focus:outline-none"
              >
                {PAGE_SIZES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-3">
              <span>{rangeStart}–{rangeEnd} of {filtered.length}</span>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage(p => p - 1)}
                  disabled={page === 1}
                  className="rounded p-1 hover:bg-slate-100 disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={page === totalPages}
                  className="rounded p-1 hover:bg-slate-100 disabled:opacity-30 transition-colors"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
