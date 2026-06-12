// Types matching backend Pydantic response schemas
// Source: docs/architecture/architecture.md section 3.2

// --- Overview ---

export interface SentimentDistribution {
  positive: number
  negative: number
  neutral: number
}

export interface CandidateMetrics {
  candidate_id: string
  username: string
  display_name: string
  total_posts: number
  total_comments: number
  average_sentiment_score: number
  sentiment_distribution: SentimentDistribution
  total_engagement: number
}

export interface OverviewData {
  candidates: CandidateMetrics[]
  last_scrape: string | null
  total_comments_analyzed: number
}

// --- Sentiment Timeline ---

export interface TimelineDataPoint {
  candidate_id: string
  candidate_username: string
  post_id: string
  post_url: string
  post_caption: string
  posted_at: string
  average_sentiment_score: number
  comment_count: number
}

export interface SentimentTimelineData {
  data_points: TimelineDataPoint[]
}

// --- Word Cloud ---

export interface WordCloudWord {
  word: string
  count: number
}

export interface WordCloudData {
  words: WordCloudWord[]
  total_unique_words: number
}

// --- Themes ---

export interface ThemeByCandidate {
  candidate_id: string
  username: string
  count: number
}

export interface ThemeData {
  theme: string
  count: number
  percentage: number
  by_candidate: ThemeByCandidate[]
}

export interface ThemesResponse {
  themes: ThemeData[]
}

// --- Posts ---

export interface PostData {
  post_id: string
  candidate_username: string
  url: string
  caption: string
  posted_at: string
  like_count: number
  comment_count: number
  positive_ratio: number
  negative_ratio: number
  average_sentiment_score: number
}

export interface PostsResponse {
  posts: PostData[]
  total: number
  limit: number
  offset: number
}

// --- Comparison ---

export interface TrendData {
  direction: 'improving' | 'declining' | 'stable'
  recent_avg: number
  previous_avg: number
  delta: number
}

export interface CandidateComparison extends CandidateMetrics {
  top_themes: Array<{ theme: string; count: number }>
  trend: TrendData
}

export interface ComparisonData {
  candidates: CandidateComparison[]
}

// --- Suggestions ---

export interface Suggestion {
  title: string
  description: string
  supporting_data: string
  priority: 'high' | 'medium' | 'low'
  categoria?: string
  acoes_concretas?: string[]
  exemplo_post?: string
  roteiro_video?: string
  publico_alvo?: string
  para_quem?: string
  impacto_esperado?: string
}

export interface SuggestionsResponse {
  suggestions: Suggestion[]
  resumo_executivo?: string
  generated_at: string
  data_snapshot: {
    total_comments_analyzed: number
    last_scrape: string | null
  }
}

// --- Competitive Analysis ---

export interface CompetitiveMetrics {
  username: string
  display_name: string | null
  total_posts: number
  total_comments: number
  average_sentiment_score: number
  total_engagement: number
  avg_likes_per_post: number
  avg_comments_per_post: number
  sentiment_distribution: SentimentDistribution
  top_themes: Array<{ theme: string; count: number }>
}

export interface CompetitiveAnalysisData {
  our_candidate: CompetitiveMetrics | null
  competitor: CompetitiveMetrics | null
  engagement_advantage: number
  sentiment_advantage: number
}

// --- Contextual Sentiment ---

export interface ContextualSentimentData {
  post_id: string
  caption_preview: string
  candidate_name: string
  total_comments: number
  total_classified: number
  apoio: number
  contra: number
  neutro: number
  apoio_percent: number
  contra_percent: number
  neutro_percent: number
  critica_candidato: number
  indignacao_tema: number
  ataque_terceiro: number
  critica_candidato_percent: number
  indignacao_tema_percent: number
  ataque_terceiro_percent: number
}

// --- Scraping ---

export interface ScrapingRunStatus {
  run_id: string
  status: string
  message: string
}

// --- Profiles ---

export interface ProfileData {
  candidate_id: string
  username: string
  full_name: string | null
  display_name: string
  cargo: string | null
  is_competitor: boolean
  biography: string
  followers_count: number
  follows_count: number
  posts_count: number
  verified: boolean
  is_private: boolean
  external_url: string | null
  category: string | null
  has_avatar: boolean
  avatar_path: string
  followers_delta: number | null
  updated_at: string | null
}

// --- Compare (ad-hoc) ---

export interface CompareResult {
  status: 'ready' | 'running' | 'not_found' | 'error'
  message: string
  username: string | null
  our_profile: ProfileData | null
  competitor_profile: ProfileData | null
  analysis: CompetitiveAnalysisData | null
}

// --- Health ---

export interface HealthStatus {
  status: 'ok' | 'degraded'
  database: string
  scheduler: string
  last_scrape: string | null
}
