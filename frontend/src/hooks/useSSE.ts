// SSE hook using fetch + ReadableStream so we can send Authorization headers.
// EventSource doesn't support custom headers — fetch streaming does.
import { useEffect, useRef, useState } from 'react'
import { supabase } from '../services/supabase'
import type { ProgressEvent } from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

interface UseSSEResult {
  events: ProgressEvent[]
  isDone: boolean
  error: string | null
}

export function useSSE(runId: string | null): UseSSEResult {
  const [events, setEvents] = useState<ProgressEvent[]>([])
  const [isDone, setIsDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!runId) return

    const controller = new AbortController()
    abortRef.current = controller

    async function stream() {
      const { data } = await supabase.auth.getSession()
      const token = data.session?.access_token
      if (!token) {
        setError('Not authenticated')
        return
      }

      let response: Response
      try {
        response = await fetch(`${BASE_URL}/api/research/runs/${runId}/stream`, {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'text/event-stream',
          },
          signal: controller.signal,
        })
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setError('Failed to connect to pipeline.')
          setIsDone(true)
        }
        return
      }

      if (!response.ok) {
        setError(`Server error: ${response.status}`)
        setIsDone(true)
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // SSE lines are separated by \n\n; each data line starts with "data: "
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''

        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data:')) continue
          try {
            const event: ProgressEvent = JSON.parse(line.slice(5).trim())
            setEvents((prev) => [...prev, event])
            if (event.event === 'complete' || event.event === 'error') {
              setIsDone(true)
              reader.cancel()
              return
            }
          } catch {
            // skip malformed chunks
          }
        }
      }

      setIsDone(true)
    }

    stream()

    return () => {
      abortRef.current?.abort()
    }
  }, [runId])

  return { events, isDone, error }
}
