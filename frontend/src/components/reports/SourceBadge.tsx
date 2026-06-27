import { ExternalLink, CheckCircle2, XCircle } from 'lucide-react'

interface SourceBadgeProps {
  url: string
  title?: string | null
  verified: boolean
  confidence: number
}

export function SourceBadge({ url, title, verified, confidence }: SourceBadgeProps) {
  const hostname = (() => {
    try { return new URL(url).hostname.replace('www.', '') }
    catch { return url }
  })()

  return (
    <div className="flex items-start gap-2 rounded-lg border border-slate-100 bg-slate-50 p-3">
      <span className="mt-0.5 shrink-0">
        {verified
          ? <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          : <XCircle className="h-4 w-4 text-amber-500" />}
      </span>
      <div className="min-w-0 flex-1">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline truncate"
        >
          {title || hostname}
          <ExternalLink className="h-3 w-3 shrink-0" />
        </a>
        <p className="mt-0.5 text-xs text-slate-500">
          Confidence: {(confidence * 100).toFixed(0)}% · {verified ? 'Verified' : 'Unverified'}
        </p>
      </div>
    </div>
  )
}
