import { useEffect, useRef } from 'react'
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import type { ProgressEvent } from '../../types'

interface ProgressStreamProps {
  events: ProgressEvent[]
  isDone: boolean
}

const eventIcons: Record<string, React.ReactNode> = {
  complete: <CheckCircle className="h-4 w-4 text-emerald-500" />,
  error:    <AlertCircle className="h-4 w-4 text-red-500" />,
}

export function ProgressStream({ events, isDone }: ProgressStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-950 p-4 font-mono text-sm text-slate-300 max-h-72 overflow-y-auto">
      {events.length === 0 && (
        <span className="text-slate-500">Connecting to pipeline…</span>
      )}
      {events.map((ev, i) => (
        <div key={i} className={clsx('flex items-start gap-2 py-0.5', ev.event === 'error' && 'text-red-400')}>
          <span className="mt-0.5 shrink-0">
            {eventIcons[ev.event] ?? <Loader2 className="h-4 w-4 animate-spin text-brand-400" />}
          </span>
          <span>{ev.message}</span>
        </div>
      ))}
      {!isDone && events.length > 0 && (
        <div className="flex items-center gap-2 py-0.5 text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Processing…</span>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
