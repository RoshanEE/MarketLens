// Axios client with auth token injection for backend API calls
import axios from 'axios'
import { supabase } from './supabase'
import type { ResearchRun, ResearchRunSummary, CreateRunPayload } from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Inject the current Supabase JWT into every request
api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const researchApi = {
  createRun: (payload: CreateRunPayload): Promise<ResearchRun> =>
    api.post<ResearchRun>('/api/research/runs', payload).then((r) => r.data),

  listRuns: (): Promise<ResearchRunSummary[]> =>
    api.get<ResearchRunSummary[]>('/api/research/runs').then((r) => r.data),

  getRun: (id: string): Promise<ResearchRun> =>
    api.get<ResearchRun>(`/api/research/runs/${id}`).then((r) => r.data),

  patchRun: (id: string, data: { title: string }): Promise<ResearchRun> =>
    api.patch<ResearchRun>(`/api/research/runs/${id}`, data).then((r) => r.data),

  deleteRun: (id: string): Promise<void> =>
    api.delete(`/api/research/runs/${id}`).then(() => undefined),
}

export default api
