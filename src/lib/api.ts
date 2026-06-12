import { API_BASE_URL } from "@/lib/constants"
import type {
  OverviewData,
  SentimentTimelineData,
  WordCloudData,
  ThemesResponse,
  PostsResponse,
  ComparisonData,
  CompetitiveAnalysisData,
  ContextualSentimentData,
  SuggestionsResponse,
  ScrapingRunStatus,
  HealthStatus,
  ProfileData,
  CompareResult,
} from "@/lib/types"

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, options)
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(
    (entry): entry is [string, string | number] => entry[1] !== undefined
  )
  if (entries.length === 0) return ""
  const searchParams = new URLSearchParams()
  for (const [key, value] of entries) {
    searchParams.set(key, String(value))
  }
  return `?${searchParams.toString()}`
}

// --- Analytics endpoints ---

export async function fetchOverview(): Promise<OverviewData> {
  return apiFetch<OverviewData>("/api/v1/analytics/overview")
}

export async function fetchSentimentTimeline(params?: {
  candidate_id?: string
  start_date?: string
  end_date?: string
}): Promise<SentimentTimelineData> {
  const query = buildQuery(params ?? {})
  return apiFetch<SentimentTimelineData>(`/api/v1/analytics/sentiment-timeline${query}`)
}

export async function fetchWordCloud(params?: {
  candidate_id?: string
}): Promise<WordCloudData> {
  const query = buildQuery(params ?? {})
  return apiFetch<WordCloudData>(`/api/v1/analytics/wordcloud${query}`)
}

export async function fetchThemes(params?: {
  candidate_id?: string
}): Promise<ThemesResponse> {
  const query = buildQuery(params ?? {})
  return apiFetch<ThemesResponse>(`/api/v1/analytics/themes${query}`)
}

export async function fetchPosts(params?: {
  candidate_id?: string
  sort_by?: string
  order?: string
  limit?: number
  offset?: number
}): Promise<PostsResponse> {
  const query = buildQuery(params ?? {})
  return apiFetch<PostsResponse>(`/api/v1/analytics/posts${query}`)
}

export async function fetchComparison(): Promise<ComparisonData> {
  return apiFetch<ComparisonData>("/api/v1/analytics/comparison")
}

export async function fetchSuggestions(params?: {
  candidate_id?: string
}): Promise<SuggestionsResponse> {
  return apiFetch<SuggestionsResponse>("/api/v1/analytics/suggestions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: params?.candidate_id
      ? JSON.stringify({ candidate_id: params.candidate_id })
      : JSON.stringify({}),
  })
}

// --- Competitive Analysis ---

export async function fetchCompetitiveAnalysis(params?: {
  our_username?: string
  competitor_username?: string
}): Promise<CompetitiveAnalysisData> {
  const query = buildQuery(params ?? {})
  return apiFetch<CompetitiveAnalysisData>(`/api/v1/analytics/competitive${query}`)
}

// --- Contextual Sentiment ---

export async function fetchContextualSentiment(postId: string): Promise<ContextualSentimentData> {
  return apiFetch<ContextualSentimentData>(`/api/v1/analysis/sentiment/contextual/${postId}`, {
    method: "POST",
  })
}

// --- Scraping endpoint ---

export async function triggerScraping(): Promise<ScrapingRunStatus> {
  return apiFetch<ScrapingRunStatus>("/api/v1/scraping/run", {
    method: "POST",
  })
}

// --- Health endpoint ---

export async function fetchHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health")
}

// --- Profiles ---

export async function fetchProfiles(): Promise<ProfileData[]> {
  return apiFetch<ProfileData[]>("/api/v1/profiles")
}

/** URL absoluta do avatar servido pelo backend (sem dependência da CDN do Instagram). */
export function avatarUrl(candidateId: string): string {
  return `${API_BASE_URL}/api/v1/profiles/${candidateId}/avatar`
}

// --- Comparação sob demanda (colar link de perfil) ---

export async function startCompare(url: string, ourId?: string): Promise<CompareResult> {
  return apiFetch<CompareResult>("/api/v1/compare/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, our_username: ourId }),
  })
}

export async function fetchCompareStatus(username: string, ourId?: string): Promise<CompareResult> {
  const query = ourId ? `?our=${encodeURIComponent(ourId)}` : ""
  return apiFetch<CompareResult>(`/api/v1/compare/${encodeURIComponent(username)}${query}`)
}
