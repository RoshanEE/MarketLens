import { useState, useRef, useEffect } from 'react'
import {
  AlertTriangle, CheckCircle2, TrendingUp, Users, Lightbulb,
  RefreshCw, ChevronDown, ChevronUp, RotateCcw, Printer,
  Globe, Tag, FileText, Loader2, Pencil, X, Check,
} from 'lucide-react'
import { ThemeCard } from './ThemeCard'
import { SourceBadge } from './SourceBadge'
import { RerunModal } from './RerunModal'
import { Badge } from '../ui/Badge'
import { Card } from '../ui/Card'
import type { CreateRunPayload, Report, ResearchRun } from '../../types'

interface ReportViewProps {
  run: ResearchRun
  report: Report
  onRerun?: (payload: CreateRunPayload) => Promise<void>
  onTitleChange?: (title: string) => Promise<void>
}

export function ReportView({ run, report, onRerun, onTitleChange }: ReportViewProps) {
  const [configOpen, setConfigOpen] = useState(false)
  const [showRerunModal, setShowRerunModal] = useState(false)
  const [rerunning, setRerunning] = useState(false)

  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState(run.title ?? '')
  const [savingTitle, setSavingTitle] = useState(false)
  const titleInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editingTitle) titleInputRef.current?.select()
  }, [editingTitle])

  const startEditTitle = () => {
    setTitleDraft(run.title ?? '')
    setEditingTitle(true)
  }

  const cancelEditTitle = () => {
    setEditingTitle(false)
    setTitleDraft(run.title ?? '')
  }

  const saveTitle = async () => {
    const trimmed = titleDraft.trim()
    if (!trimmed || trimmed === run.title || !onTitleChange) {
      setEditingTitle(false)
      return
    }
    setSavingTitle(true)
    try {
      await onTitleChange(trimmed)
      setEditingTitle(false)
    } finally {
      setSavingTitle(false)
    }
  }

  const titleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') saveTitle()
    if (e.key === 'Escape') cancelEditTitle()
  }

  const confidence = report.overall_confidence ?? 0
  const confVariant = confidence >= 0.75 ? 'success' : confidence >= 0.5 ? 'warning' : 'error'
  const verified = report.hallucination_results?.verified_claims ?? 0
  const total = report.hallucination_results?.total_claims ?? 0

  const handleRerun = async (payload: CreateRunPayload) => {
    if (!onRerun) return
    setRerunning(true)
    try {
      await onRerun(payload)
      setShowRerunModal(false)
    } finally {
      setRerunning(false)
    }
  }

  return (
    <div className="space-y-6">

      {/* ── Report header ─────────────────────────────────────────── */}
      <Card>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            {editingTitle ? (
              <div className="flex items-center gap-2">
                <input
                  ref={titleInputRef}
                  className="input py-1 text-xl font-bold"
                  value={titleDraft}
                  onChange={e => setTitleDraft(e.target.value)}
                  onKeyDown={titleKeyDown}
                  disabled={savingTitle}
                />
                <button
                  onClick={saveTitle}
                  disabled={savingTitle}
                  className="rounded-lg p-1.5 text-emerald-600 hover:bg-emerald-50 transition-colors"
                  title="Save"
                >
                  {savingTitle ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                </button>
                <button
                  onClick={cancelEditTitle}
                  disabled={savingTitle}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 transition-colors"
                  title="Cancel"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 group">
                <h2 className="text-xl font-bold text-slate-900 truncate">
                  {run.title ?? 'Research Report'}
                </h2>
                {onTitleChange && (
                  <button
                    onClick={startEditTitle}
                    className="rounded p-1 text-slate-300 opacity-0 group-hover:opacity-100 hover:text-slate-600 hover:bg-slate-100 transition-all print:hidden"
                    title="Edit title"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )}
            <p className="mt-1 text-xs text-slate-400">
              {new Date(run.created_at).toLocaleString()}
              {run.completed_at && (
                <> · completed {new Date(run.completed_at).toLocaleString()}</>
              )}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge variant={confVariant}>{(confidence * 100).toFixed(0)}% confidence</Badge>
              <Badge variant="info">{verified}/{total} claims verified</Badge>
              {report.changes_detected.length > 0 && (
                <Badge variant="warning">{report.changes_detected.length} change{report.changes_detected.length !== 1 ? 's' : ''} detected</Badge>
              )}
            </div>
          </div>

          {/* Action buttons — hidden when printing */}
          <div className="flex shrink-0 gap-2 print:hidden">
            {onRerun && (
              <button
                onClick={() => setShowRerunModal(true)}
                disabled={rerunning}
                className="btn-secondary py-1.5 text-xs"
                title="Run again with editable configuration"
              >
                {rerunning
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <RotateCcw className="h-3.5 w-3.5" />}
                Run Again
              </button>
            )}
            <button
              onClick={() => window.print()}
              className="btn-secondary py-1.5 text-xs"
              title="Export as PDF via browser print dialog"
            >
              <Printer className="h-3.5 w-3.5" />
              Export PDF
            </button>
          </div>
        </div>

        {/* Run configuration (collapsible) */}
        <div className="mt-4 border-t border-slate-100 pt-4">
          <button
            onClick={() => setConfigOpen(o => !o)}
            className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-700 transition-colors print:hidden"
          >
            <FileText className="h-3.5 w-3.5" />
            Run configuration
            {configOpen
              ? <ChevronUp className="h-3.5 w-3.5" />
              : <ChevronDown className="h-3.5 w-3.5" />}
          </button>

          {configOpen && (
            <div className="mt-3 space-y-3 text-sm">
              {run.competitors.length > 0 && (
                <div className="flex items-start gap-2">
                  <Users className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-slate-500 mb-1">Competitors</p>
                    <div className="flex flex-wrap gap-1.5">
                      {run.competitors.map(c => (
                        <span key={c} className="rounded-full bg-violet-50 border border-violet-100 px-2.5 py-0.5 text-xs text-violet-700">{c}</span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              {run.topics.length > 0 && (
                <div className="flex items-start gap-2">
                  <Tag className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-slate-500 mb-1">Topics</p>
                    <div className="flex flex-wrap gap-1.5">
                      {run.topics.map(t => (
                        <span key={t} className="rounded-full bg-brand-50 border border-brand-100 px-2.5 py-0.5 text-xs text-brand-700">{t}</span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              {run.context && (
                <div className="flex items-start gap-2">
                  <FileText className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-slate-500 mb-1">Context</p>
                    <p className="text-xs text-slate-600">{run.context}</p>
                  </div>
                </div>
              )}
              <div className="flex items-start gap-2">
                <Globe className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-1">Sources ({run.source_urls.length})</p>
                  <div className="space-y-1.5">
                    {run.source_urls.map(src => (
                      <div key={src.id} className="flex items-center gap-2">
                        {src.crawl_status === 'success'
                          ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                          : <AlertTriangle className="h-3.5 w-3.5 text-red-400 shrink-0" />}
                        <a
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="truncate text-xs text-brand-600 hover:underline"
                        >
                          {src.page_title || src.url}
                        </a>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* ── Change detection notice ──────────────────────────────── */}
      {report.changes_detected.length > 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <RefreshCw className="mt-0.5 h-4 w-4 text-amber-600 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800">Changes detected since last run</p>
            <ul className="mt-1 list-inside list-disc text-sm text-amber-700">
              {report.changes_detected.map((c, i) => (
                <li key={i}>{c.url} — {c.type.replace('_', ' ')}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* ── Low confidence warning ───────────────────────────────── */}
      {confidence < 0.5 && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-red-600 shrink-0" />
          <p className="text-sm text-red-700">
            Low confidence score — many claims could not be directly verified against source content.
            Review source links carefully before acting on these insights.
          </p>
        </div>
      )}

      {/* ── Key Insights ─────────────────────────────────────────── */}
      {report.key_insights.length > 0 && (
        <section>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-900">
            <Lightbulb className="h-5 w-5 text-amber-500" /> Key Insights
          </h2>
          <div className="space-y-3">
            {report.key_insights.map((insight, i) => (
              <div key={i} className="rounded-xl border border-slate-200 bg-white p-4 space-y-2">
                <p className="text-sm font-medium text-slate-800">{insight.claim}</p>
                <SourceBadge
                  url={insight.source_url}
                  title={insight.source_title}
                  verified={insight.verified}
                  confidence={insight.confidence}
                />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Market Themes ────────────────────────────────────────── */}
      {report.themes.length > 0 && (
        <section>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-900">
            <TrendingUp className="h-5 w-5 text-brand-600" /> Market Themes
          </h2>
          <div className="space-y-3">
            {report.themes.map((theme, i) => (
              <ThemeCard key={i} theme={theme} index={i} />
            ))}
          </div>
        </section>
      )}

      {/* ── Competitor Activity ──────────────────────────────────── */}
      {report.competitor_activities.length > 0 && (
        <section>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-900">
            <Users className="h-5 w-5 text-violet-600" /> Competitor Activity
          </h2>
          <div className="space-y-4">
            {report.competitor_activities.map((ca, i) => (
              <Card key={i}>
                <h3 className="font-semibold text-slate-900 mb-3">{ca.competitor}</h3>
                <div className="space-y-3">
                  {ca.activities.map((act, j) => (
                    <div key={j} className="space-y-1.5">
                      <p className="text-sm text-slate-800">{act.claim}</p>
                      <SourceBadge
                        url={act.source_url}
                        title={act.source_title}
                        verified={act.verified}
                        confidence={act.confidence}
                      />
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* ── Rerun modal ──────────────────────────────────────────── */}
      {showRerunModal && (
        <RerunModal
          run={run}
          submitting={rerunning}
          onSubmit={handleRerun}
          onClose={() => setShowRerunModal(false)}
        />
      )}
    </div>
  )
}
