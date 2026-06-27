import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { SourceBadge } from './SourceBadge'
import { Card } from '../ui/Card'
import type { Theme } from '../../types'

interface ThemeCardProps {
  theme: Theme
  index: number
}

export function ThemeCard({ theme, index }: ThemeCardProps) {
  const [expanded, setExpanded] = useState(index === 0)

  return (
    <Card padding={false}>
      <button
        className="flex w-full items-center justify-between p-5 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <div>
          <h3 className="font-semibold text-slate-900">{theme.title}</h3>
          <p className="mt-1 text-sm text-slate-500">{theme.insights.length} insight{theme.insights.length !== 1 ? 's' : ''}</p>
        </div>
        {expanded ? <ChevronUp className="h-5 w-5 text-slate-400" /> : <ChevronDown className="h-5 w-5 text-slate-400" />}
      </button>

      {expanded && (
        <div className="border-t border-slate-100 p-5 space-y-4">
          <p className="text-sm text-slate-700 leading-relaxed">{theme.summary}</p>

          <div className="space-y-3">
            {theme.insights.map((insight, i) => (
              <div key={i} className="space-y-1.5">
                <p className="text-sm text-slate-800">{insight.claim}</p>
                {insight.judge_reasoning && !insight.verified && (
                  <p className="text-xs text-amber-600 italic">Note: {insight.judge_reasoning}</p>
                )}
                <SourceBadge
                  url={insight.source_url}
                  title={insight.source_title}
                  verified={insight.verified}
                  confidence={insight.confidence}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}
