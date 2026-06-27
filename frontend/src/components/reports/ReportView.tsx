import { AlertTriangle, CheckCircle2, TrendingUp, Users, Lightbulb, RefreshCw } from 'lucide-react'
import { ThemeCard } from './ThemeCard'
import { SourceBadge } from './SourceBadge'
import { Badge } from '../ui/Badge'
import { Card } from '../ui/Card'
import type { Report, ResearchRun } from '../../types'

interface ReportViewProps {
  run: ResearchRun
  report: Report
}

export function ReportView({ run, report }: ReportViewProps) {
  const confidence = report.overall_confidence ?? 0
  const confVariant = confidence >= 0.75 ? 'success' : confidence >= 0.5 ? 'warning' : 'error'

  return (
    <div className="space-y-8">
      {/* Summary bar */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">{run.title ?? 'Research Report'}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {run.competitors.length > 0 && <span>Competitors: {run.competitors.join(', ')} · </span>}
              {run.topics.length > 0 && <span>Topics: {run.topics.join(', ')}</span>}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant={confVariant}>
              {(confidence * 100).toFixed(0)}% confidence
            </Badge>
            <Badge variant="info">
              {report.hallucination_results?.verified_claims ?? 0}/{report.hallucination_results?.total_claims ?? 0} claims verified
            </Badge>
          </div>
        </div>
      </Card>

      {/* Change detection notice */}
      {report.changes_detected.length > 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <RefreshCw className="mt-0.5 h-4 w-4 text-amber-600 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800">Changes detected since last run</p>
            <ul className="mt-1 text-sm text-amber-700 list-disc list-inside">
              {report.changes_detected.map((c, i) => (
                <li key={i}>{c.url} — {c.type.replace('_', ' ')}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Hallucination warning */}
      {confidence < 0.5 && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-red-600 shrink-0" />
          <p className="text-sm text-red-700">
            Low confidence score detected. Many claims could not be directly verified against source content.
            Review the source links carefully before acting on these insights.
          </p>
        </div>
      )}

      {/* Key Insights */}
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

      {/* Themes */}
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

      {/* Competitor Activities */}
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

      {/* Source URLs */}
      <section>
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Sources Crawled</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {run.source_urls.map((src) => (
            <div key={src.id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3">
              {src.crawl_status === 'success'
                ? <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                : <AlertTriangle className="h-4 w-4 text-red-400 shrink-0" />}
              <div className="min-w-0">
                <a
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block truncate text-xs font-medium text-brand-600 hover:underline"
                >
                  {src.page_title || src.url}
                </a>
                {src.error && <p className="text-xs text-red-500 mt-0.5">{src.error}</p>}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
