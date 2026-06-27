// Domain types matching the backend Pydantic schemas

export type RunStatus = 'pending' | 'crawling' | 'analyzing' | 'judging' | 'complete' | 'failed'

export interface SourceUrl {
  id: string
  url: string
  page_title: string | null
  crawl_status: string
  error: string | null
  crawled_at: string | null
}

export interface Insight {
  claim: string
  source_url: string
  source_title: string | null
  confidence: number
  verified: boolean
  judge_reasoning: string | null
}

export interface Theme {
  title: string
  summary: string
  insights: Insight[]
}

export interface CompetitorActivity {
  competitor: string
  activities: Insight[]
}

export interface HallucinationResults {
  total_claims: number
  verified_claims: number
  unverified_claims: number
  overall_confidence: number | null
  confidence_threshold: number
}

export interface Report {
  id: string
  run_id: string
  themes: Theme[]
  competitor_activities: CompetitorActivity[]
  key_insights: Insight[]
  overall_confidence: number | null
  changes_detected: Array<{ url: string; type: string }>
  hallucination_results?: HallucinationResults
  created_at: string
}

export interface ResearchRun {
  id: string
  title: string | null
  competitors: string[]
  topics: string[]
  context: string | null
  status: RunStatus
  error: string | null
  created_at: string
  completed_at: string | null
  source_urls: SourceUrl[]
  report: Report | null
}

export interface ResearchRunSummary {
  id: string
  title: string | null
  competitors: string[]
  topics: string[]
  status: RunStatus
  created_at: string
  completed_at: string | null
  url_count: number
}

export interface ProgressEvent {
  event: 'crawling' | 'analyzing' | 'judging' | 'complete' | 'error'
  message: string
  detail?: Record<string, unknown>
}

export interface CreateRunPayload {
  title?: string
  competitors: string[]
  topics: string[]
  urls: string[]
  context?: string
}
