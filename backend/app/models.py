"""Schemas Pydantic — espelham exatamente src/lib/types.ts do frontend."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class SentimentDistribution(BaseModel):
    positive: int = 0
    negative: int = 0
    neutral: int = 0


class CandidateMetrics(BaseModel):
    candidate_id: str
    username: str
    display_name: str
    total_posts: int
    total_comments: int
    average_sentiment_score: float
    sentiment_distribution: SentimentDistribution
    total_engagement: int


class OverviewData(BaseModel):
    candidates: list[CandidateMetrics]
    last_scrape: Optional[str] = None
    total_comments_analyzed: int


class TimelineDataPoint(BaseModel):
    candidate_id: str
    candidate_username: str
    post_id: str
    post_url: str
    post_caption: str
    posted_at: str
    average_sentiment_score: float
    comment_count: int


class SentimentTimelineData(BaseModel):
    data_points: list[TimelineDataPoint]


class WordCloudWord(BaseModel):
    word: str
    count: int


class WordCloudData(BaseModel):
    words: list[WordCloudWord]
    total_unique_words: int


class ThemeByCandidate(BaseModel):
    candidate_id: str
    username: str
    count: int


class ThemeData(BaseModel):
    theme: str
    count: int
    percentage: float
    by_candidate: list[ThemeByCandidate]


class ThemesResponse(BaseModel):
    themes: list[ThemeData]


class PostData(BaseModel):
    post_id: str
    candidate_username: str
    url: str
    caption: str
    posted_at: str
    like_count: int
    comment_count: int
    positive_ratio: float
    negative_ratio: float
    average_sentiment_score: float


class PostsResponse(BaseModel):
    posts: list[PostData]
    total: int
    limit: int
    offset: int


class ThemeCount(BaseModel):
    theme: str
    count: int


class TrendData(BaseModel):
    direction: Literal["improving", "declining", "stable"]
    recent_avg: float
    previous_avg: float
    delta: float


class CandidateComparison(CandidateMetrics):
    top_themes: list[ThemeCount]
    trend: TrendData


class ComparisonData(BaseModel):
    candidates: list[CandidateComparison]


class Suggestion(BaseModel):
    title: str
    description: str
    supporting_data: str
    priority: Literal["high", "medium", "low"]
    categoria: Optional[str] = None
    acoes_concretas: Optional[list[str]] = None
    exemplo_post: Optional[str] = None
    roteiro_video: Optional[str] = None
    publico_alvo: Optional[str] = None
    para_quem: Optional[str] = None
    impacto_esperado: Optional[str] = None


class DataSnapshot(BaseModel):
    total_comments_analyzed: int
    last_scrape: Optional[str] = None


class SuggestionsResponse(BaseModel):
    suggestions: list[Suggestion]
    resumo_executivo: Optional[str] = None
    generated_at: str
    data_snapshot: DataSnapshot


class CompetitiveMetrics(BaseModel):
    username: str
    display_name: Optional[str] = None
    total_posts: int
    total_comments: int
    average_sentiment_score: float
    total_engagement: int
    avg_likes_per_post: float
    avg_comments_per_post: float
    sentiment_distribution: SentimentDistribution
    top_themes: list[ThemeCount]


class CompetitiveAnalysisData(BaseModel):
    our_candidate: Optional[CompetitiveMetrics] = None
    competitor: Optional[CompetitiveMetrics] = None
    engagement_advantage: float
    sentiment_advantage: float


class ContextualSentimentData(BaseModel):
    post_id: str
    caption_preview: str
    candidate_name: str
    total_comments: int
    total_classified: int
    apoio: int
    contra: int
    neutro: int
    apoio_percent: float
    contra_percent: float
    neutro_percent: float


class ScrapingRunStatus(BaseModel):
    run_id: str
    status: str
    message: str


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    database: str
    scheduler: str
    last_scrape: Optional[str] = None


class SuggestionsRequest(BaseModel):
    candidate_id: Optional[str] = None
