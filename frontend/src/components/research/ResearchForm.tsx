import { useState, KeyboardEvent } from 'react'
import { X, Plus } from 'lucide-react'
import { Spinner } from '../ui/Spinner'
import type { CreateRunPayload } from '../../types'

interface ResearchFormProps {
  onSubmit: (payload: CreateRunPayload) => Promise<void>
  loading: boolean
  initialValues?: Omit<CreateRunPayload, 'title'>
  hideTitle?: boolean
  submitLabel?: string
}

export function ResearchForm({ onSubmit, loading, initialValues, hideTitle = false, submitLabel }: ResearchFormProps) {
  const [competitors, setCompetitors] = useState<string[]>(() => initialValues?.competitors ?? [])
  const [topics, setTopics] = useState<string[]>(() => initialValues?.topics ?? [])
  const [urls, setUrls] = useState<string[]>(() =>
    initialValues?.urls?.length ? [...initialValues.urls] : ['']
  )
  const [context, setContext] = useState(() => initialValues?.context ?? '')
  const [title, setTitle] = useState('')

  const [competitorInput, setCompetitorInput] = useState('')
  const [topicInput, setTopicInput] = useState('')
  const [error, setError] = useState<string | null>(null)

  const addTag = (
    value: string,
    list: string[],
    setList: (v: string[]) => void,
    setInput: (v: string) => void,
  ) => {
    const trimmed = value.trim()
    if (trimmed && !list.includes(trimmed)) setList([...list, trimmed])
    setInput('')
  }

  const removeTag = (index: number, list: string[], setList: (v: string[]) => void) =>
    setList(list.filter((_, i) => i !== index))

  const handleUrlChange = (index: number, value: string) => {
    const updated = [...urls]
    updated[index] = value
    setUrls(updated)
  }

  const addUrl = () => setUrls([...urls, ''])
  const removeUrl = (index: number) => setUrls(urls.filter((_, i) => i !== index))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const validUrls = urls.filter((u) => u.trim())
    if (competitors.length === 0 && topics.length === 0) {
      setError('Add at least one competitor or topic.')
      return
    }
    if (validUrls.length === 0) {
      setError('Add at least one URL.')
      return
    }

    try {
      await onSubmit({ title: title.trim() || undefined, competitors, topics, urls: validUrls, context: context.trim() || undefined })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Something went wrong.'
      setError(msg)
    }
  }

  const tagKeyDown = (
    e: KeyboardEvent<HTMLInputElement>,
    value: string,
    list: string[],
    setList: (v: string[]) => void,
    setInput: (v: string) => void,
  ) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addTag(value, list, setList, setInput)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Title */}
      {!hideTitle && (
        <div>
          <label className="label">Research Title (optional)</label>
          <input
            className="input"
            placeholder="e.g. Q3 Competitor Analysis"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
      )}

      {/* Competitors */}
      <div>
        <label className="label">Competitors</label>
        <div className="flex flex-wrap gap-2 mb-2">
          {competitors.map((c, i) => (
            <span key={i} className="flex items-center gap-1 rounded-full bg-brand-100 px-3 py-1 text-xs font-medium text-brand-700">
              {c}
              <button type="button" onClick={() => removeTag(i, competitors, setCompetitors)}>
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
        <input
          className="input"
          placeholder="Type a competitor name and press Enter"
          value={competitorInput}
          onChange={(e) => setCompetitorInput(e.target.value)}
          onKeyDown={(e) => tagKeyDown(e, competitorInput, competitors, setCompetitors, setCompetitorInput)}
          onBlur={() => addTag(competitorInput, competitors, setCompetitors, setCompetitorInput)}
        />
      </div>

      {/* Topics */}
      <div>
        <label className="label">Topics / Keywords</label>
        <div className="flex flex-wrap gap-2 mb-2">
          {topics.map((t, i) => (
            <span key={i} className="flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700">
              {t}
              <button type="button" onClick={() => removeTag(i, topics, setTopics)}>
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
        <input
          className="input"
          placeholder="e.g. AI features, pricing, partnerships"
          value={topicInput}
          onChange={(e) => setTopicInput(e.target.value)}
          onKeyDown={(e) => tagKeyDown(e, topicInput, topics, setTopics, setTopicInput)}
          onBlur={() => addTag(topicInput, topics, setTopics, setTopicInput)}
        />
      </div>

      {/* Source URLs */}
      <div>
        <label className="label">Source URLs</label>
        <div className="space-y-2">
          {urls.map((url, i) => (
            <div key={i} className="flex gap-2">
              <input
                className="input flex-1"
                type="url"
                placeholder="https://example.com/blog/announcement"
                value={url}
                onChange={(e) => handleUrlChange(i, e.target.value)}
              />
              {urls.length > 1 && (
                <button type="button" onClick={() => removeUrl(i)} className="text-slate-400 hover:text-red-500">
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
        </div>
        <button type="button" onClick={addUrl} className="mt-2 flex items-center gap-1 text-sm text-brand-600 hover:underline">
          <Plus className="h-4 w-4" /> Add another URL
        </button>
      </div>

      {/* Context */}
      <div>
        <label className="label">Additional Context (optional)</label>
        <textarea
          className="input resize-none"
          rows={3}
          placeholder="e.g. Focus on enterprise AI features launched in the last 6 months"
          value={context}
          onChange={(e) => setContext(e.target.value)}
        />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-3">
        {loading ? <><Spinner size="sm" /> Running Research…</> : (submitLabel ?? 'Run Market Intelligence Analysis')}
      </button>
    </form>
  )
}
