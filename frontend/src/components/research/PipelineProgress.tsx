import { CheckCircle2, AlertCircle, Loader2, Globe, Sparkles, ShieldCheck, Flag, RefreshCw } from 'lucide-react'
import { clsx } from 'clsx'
import type { ProgressEvent } from '../../types'

const STAGES = [
  { id: 'crawling',  label: 'Crawl Sources', Icon: Globe },
  { id: 'analyzing', label: 'AI Analysis',   Icon: Sparkles },
  { id: 'judging',   label: 'Verify Claims', Icon: ShieldCheck },
  { id: 'complete',  label: 'Complete',      Icon: Flag },
] as const

const STAGE_IDS = STAGES.map(s => s.id)
type StageId = (typeof STAGES)[number]['id']
type StageStatus = 'pending' | 'active' | 'done' | 'error'

// Last event that belongs to a pipeline stage (excludes terminal 'error' events)
function currentPipelineStage(events: ProgressEvent[]): StageId | null {
  const last = [...events].reverse().find(e => STAGE_IDS.includes(e.event as StageId))
  return (last?.event as StageId) ?? null
}

function stageStatus(
  id: StageId,
  current: StageId | null,
  hasError: boolean,
  isDone: boolean,
): StageStatus {
  if (!current) return 'pending'
  const si = STAGE_IDS.indexOf(id)
  const ci = STAGE_IDS.indexOf(current)
  if (si < ci) return 'done'
  if (si === ci) {
    if (hasError) return 'error'
    if (isDone) return 'done'
    return 'active'
  }
  return 'pending'
}

interface PipelineProgressProps {
  events: ProgressEvent[]
  isDone: boolean
  onViewReport: () => void
  onRetry?: () => void
}

export function PipelineProgress({ events, isDone, onViewReport, onRetry }: PipelineProgressProps) {
  const hasError = isDone && events.at(-1)?.event === 'error'
  const isComplete = isDone && !hasError
  const current = currentPipelineStage(events)

  // Group events by their pipeline stage id
  const byStage: Partial<Record<StageId, ProgressEvent[]>> = {}
  for (const ev of events) {
    if (STAGE_IDS.includes(ev.event as StageId)) {
      const key = ev.event as StageId
      byStage[key] = [...(byStage[key] ?? []), ev]
    }
  }

  const startedStages = STAGES.filter(s => (byStage[s.id]?.length ?? 0) > 0)

  return (
    <div className="space-y-6">
      {/* ── Stepper ───────────────────────────────────────────────── */}
      <div className="flex items-start">
        {STAGES.map((stage, i) => {
          const status = stageStatus(stage.id, current, hasError, isDone)
          const isLast = i === STAGES.length - 1
          // Line after stage i is filled once the next stage has started
          const lineFilled = current !== null && STAGE_IDS.indexOf(current) > i

          return (
            <div key={stage.id} className="flex items-start flex-1 min-w-0">
              <div className="flex flex-col items-center gap-1">
                <div className={clsx(
                  'flex h-8 w-8 items-center justify-center rounded-full border-2 transition-colors shrink-0',
                  status === 'done'    && 'border-emerald-500 bg-emerald-500',
                  status === 'active'  && 'border-brand-500 bg-brand-50',
                  status === 'error'   && 'border-red-400 bg-red-50',
                  status === 'pending' && 'border-slate-200 bg-white',
                )}>
                  {status === 'done'    && <CheckCircle2 className="h-4 w-4 text-white" />}
                  {status === 'active'  && <Loader2 className="h-4 w-4 text-brand-500 animate-spin" />}
                  {status === 'error'   && <AlertCircle className="h-4 w-4 text-red-400" />}
                  {status === 'pending' && <stage.Icon className="h-4 w-4 text-slate-300" />}
                </div>
                <span className={clsx(
                  'text-xs font-medium text-center leading-tight whitespace-nowrap',
                  status === 'done'    && 'text-emerald-600',
                  status === 'active'  && 'text-brand-600',
                  status === 'error'   && 'text-red-500',
                  status === 'pending' && 'text-slate-400',
                )}>
                  {stage.label}
                </span>
              </div>

              {!isLast && (
                <div className={clsx(
                  'h-0.5 flex-1 mt-4 mx-2 transition-colors duration-500',
                  lineFilled ? 'bg-emerald-400' : 'bg-slate-200',
                )} />
              )}
            </div>
          )
        })}
      </div>

      {/* ── Stage cards ───────────────────────────────────────────── */}
      {events.length === 0 ? (
        <p className="py-4 text-center text-sm text-slate-400">Connecting to pipeline…</p>
      ) : (
        <div className="space-y-3">
          {startedStages.map(stage => {
            const msgs = byStage[stage.id] ?? []
            const status = stageStatus(stage.id, current, hasError, isDone)
            const failedUrls = msgs.flatMap(e => (e.detail?.failed as string[] | undefined) ?? [])
            const changes = (msgs.at(-1)?.detail?.changes as Array<{ url: string; type: string }> | undefined) ?? []

            return (
              <div
                key={stage.id}
                className={clsx(
                  'rounded-lg border p-4 transition-colors',
                  status === 'done'   && 'border-emerald-100 bg-emerald-50',
                  status === 'active' && 'border-brand-100 bg-brand-50',
                  status === 'error'  && 'border-red-100 bg-red-50',
                )}
              >
                {/* Card header */}
                <div className="mb-2 flex items-center gap-2">
                  {status === 'done'   && <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />}
                  {status === 'active' && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-500" />}
                  {status === 'error'  && <AlertCircle className="h-4 w-4 shrink-0 text-red-500" />}
                  <span className={clsx(
                    'text-sm font-semibold',
                    status === 'done'   && 'text-emerald-700',
                    status === 'active' && 'text-brand-700',
                    status === 'error'  && 'text-red-700',
                  )}>
                    {stage.label}
                  </span>
                </div>

                {/* Stage messages */}
                <div className="space-y-0.5 pl-6">
                  {msgs.map((ev, i) => (
                    <p key={i} className="text-sm text-slate-600">{ev.message}</p>
                  ))}

                  {/* Failed URLs from crawling detail */}
                  {failedUrls.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {failedUrls.map(url => (
                        <li key={url} className="text-xs text-red-500">✗ {url}</li>
                      ))}
                    </ul>
                  )}

                  {/* Change detection summary on complete card */}
                  {stage.id === 'complete' && changes.length > 0 && (
                    <div className="mt-2">
                      <p className="mb-1 text-xs font-medium text-slate-500">
                        {changes.length} URL(s) changed since last run
                      </p>
                      <ul className="space-y-0.5">
                        {changes.map(c => (
                          <li key={c.url} className="text-xs text-slate-500">• {c.url}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* View Report CTA — separated from stage messages */}
                {stage.id === 'complete' && isComplete && (
                  <div className="mt-5 border-t border-emerald-200 pt-4">
                    <button onClick={onViewReport} className="btn-primary">
                      View Report →
                    </button>
                  </div>
                )}
              </div>
            )
          })}

          {/* Terminal error block — 'error' is not a pipeline stage so it gets its own card */}
          {hasError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4">
              <div className="mb-1 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-red-500" />
                <span className="text-sm font-semibold text-red-700">Pipeline failed</span>
              </div>
              <p className="pl-6 text-sm text-red-600">
                {events.at(-1)?.message ?? 'An unexpected error occurred.'}
              </p>
              {onRetry && (
                <div className="mt-3 pl-6">
                  <button onClick={onRetry} className="btn-secondary text-sm">
                    <RefreshCw className="h-3.5 w-3.5" />
                    Retry from beginning
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
