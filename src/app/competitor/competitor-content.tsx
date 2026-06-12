"use client"

import { useState } from "react"
import {
  Swords,
  TrendingUp,
  TrendingDown,
  Minus,
  Users,
  Heart,
  MessageCircle,
  Loader2,
  Sparkles,
  Brain,
  ExternalLink,
} from "lucide-react"
import { useCompetitive } from "@/hooks/use-competitive"
import { fetchSuggestions } from "@/lib/api"
import { useOverview } from "@/hooks/use-overview"
import { getCandidateId, formatThemeLabel } from "@/lib/utils"
import type { CompetitiveMetrics } from "@/lib/types"
import type { Suggestion, SuggestionsResponse } from "@/lib/types"
import {
  CANDIDATE_B_DISPLAY,
  COMPETITOR_DISPLAY,
} from "@/lib/constants"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { ErrorMessage } from "@/components/shared/error-message"
import { SuggestionCard } from "@/components/dashboard/suggestion-card"
import { ComparePanel } from "@/components/profile/compare-panel"

function MetricComparison({
  label,
  ourValue,
  theirValue,
  format = "number",
}: {
  label: string
  ourValue: number
  theirValue: number
  format?: "number" | "decimal" | "sentiment"
}) {
  const diff = ourValue - theirValue
  const isWinning = diff > 0
  const isTied = Math.abs(diff) < 0.01

  function formatValue(v: number) {
    if (format === "decimal") return v.toFixed(1)
    if (format === "sentiment") return v.toFixed(2)
    return v.toLocaleString("pt-BR")
  }

  return (
    <div className="flex items-center justify-between rounded-lg border border-border/30 bg-secondary/20 p-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="flex items-center gap-4">
        <span className="text-sm font-semibold text-blue-300">
          {formatValue(ourValue)}
        </span>
        <span className="text-xs text-muted-foreground/50">vs</span>
        <span className="text-sm font-semibold text-red-300">
          {formatValue(theirValue)}
        </span>
        {isTied ? (
          <Minus className="h-4 w-4 text-muted-foreground" />
        ) : isWinning ? (
          <TrendingUp className="h-4 w-4 text-emerald-400" />
        ) : (
          <TrendingDown className="h-4 w-4 text-red-400" />
        )}
      </div>
    </div>
  )
}

function CandidateColumn({
  metrics,
  color,
  isCompetitor = false,
}: {
  metrics: CompetitiveMetrics
  color: string
  isCompetitor?: boolean
}) {
  return (
    <Card className={isCompetitor ? "border-red-800/30" : "border-blue-800/30"}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg text-white">
            {metrics.display_name ?? metrics.username}
          </CardTitle>
          {isCompetitor && (
            <Badge variant="outline" className="bg-red-900/30 text-red-300 border-red-700/50">
              Concorrente
            </Badge>
          )}
        </div>
        <a
          href={`https://instagram.com/${metrics.username}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          @{metrics.username}
          <ExternalLink className="h-3 w-3" />
        </a>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 text-center">
          <div className="rounded-lg bg-secondary/30 p-3">
            <p className="text-xl font-bold text-white">{metrics.total_posts}</p>
            <p className="text-xs text-muted-foreground">Posts</p>
          </div>
          <div className="rounded-lg bg-secondary/30 p-3">
            <p className="text-xl font-bold text-white">{metrics.total_comments}</p>
            <p className="text-xs text-muted-foreground">Comentários</p>
          </div>
          <div className="rounded-lg bg-secondary/30 p-3">
            <div className="flex items-center justify-center gap-1">
              <Heart className="h-3 w-3" style={{ color }} />
              <p className="text-xl font-bold text-white">
                {metrics.avg_likes_per_post.toFixed(0)}
              </p>
            </div>
            <p className="text-xs text-muted-foreground">Curtidas/Post</p>
          </div>
          <div className="rounded-lg bg-secondary/30 p-3">
            <div className="flex items-center justify-center gap-1">
              <MessageCircle className="h-3 w-3" style={{ color }} />
              <p className="text-xl font-bold text-white">
                {metrics.avg_comments_per_post.toFixed(0)}
              </p>
            </div>
            <p className="text-xs text-muted-foreground">Comentários/Post</p>
          </div>
        </div>

        {/* Sentiment */}
        <div className="rounded-lg border border-border/20 bg-secondary/10 p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Sentimento Médio</p>
          <p className={`text-lg font-bold ${metrics.average_sentiment_score >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {metrics.average_sentiment_score.toFixed(2)}
          </p>
          <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
            <span className="text-emerald-400">{metrics.sentiment_distribution.positive} positivos</span>
            <span className="text-red-400">{metrics.sentiment_distribution.negative} negativos</span>
            <span>{metrics.sentiment_distribution.neutral} neutros</span>
          </div>
        </div>

        {/* Themes */}
        {metrics.top_themes.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">Temas Mais Citados</p>
            <div className="flex flex-wrap gap-1.5">
              {metrics.top_themes.map((t) => (
                <Badge key={t.theme} variant="secondary" className="text-xs bg-secondary/50">
                  {formatThemeLabel(t.theme)} ({t.count})
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

const PRIORITY_ORDER: Record<Suggestion["priority"], number> = {
  high: 0,
  medium: 1,
  low: 2,
}

export function CompetitorContent() {
  const { data, loading, error, refetch } = useCompetitive()
  const { data: overviewData } = useOverview()

  const [generating, setGenerating] = useState(false)
  const [strategyData, setStrategyData] = useState<SuggestionsResponse | null>(null)
  const [strategyError, setStrategyError] = useState<Error | null>(null)

  const sheila_id = overviewData?.candidates
    ? getCandidateId("sheila", overviewData.candidates)
    : undefined

  const handleGenerateStrategy = async () => {
    setGenerating(true)
    setStrategyError(null)
    try {
      const result = await fetchSuggestions({ candidate_id: sheila_id })
      setStrategyData(result)
    } catch (err) {
      setStrategyError(
        err instanceof Error ? err : new Error("Falha ao gerar estratégia competitiva.")
      )
    } finally {
      setGenerating(false)
    }
  }

  const sortedSuggestions = strategyData?.suggestions
    ? [...strategyData.suggestions].sort(
        (a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
      )
    : []

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-red-500 to-orange-600">
            <Swords className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Inteligência Competitiva
            </h1>
            <p className="text-sm text-muted-foreground">
              {CANDIDATE_B_DISPLAY} vs {COMPETITOR_DISPLAY} — Análise de engajamento e estratégia
            </p>
          </div>
        </div>
      </div>

      {/* Comparar com qualquer perfil (colar link) */}
      <div className="mt-6">
        <ComparePanel ourId="sheila" />
      </div>

      <div className="mt-8 space-y-8">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Concorrente acompanhada — {COMPETITOR_DISPLAY}
          </span>
          <div className="h-px flex-1 bg-border/40" />
        </div>

        {/* Loading */}
        {loading && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <LoadingSkeleton variant="card" />
            <LoadingSkeleton variant="card" />
          </div>
        )}

        {/* Error */}
        {error && <ErrorMessage error={error} onRetry={refetch} />}

        {/* Side by side cards */}
        {!loading && !error && data && (
          <>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {data.our_candidate && (
                <CandidateColumn
                  metrics={data.our_candidate}
                  color="var(--color-candidate-b)"
                />
              )}
              {data.competitor && (
                <CandidateColumn
                  metrics={data.competitor}
                  color="#ef4444"
                  isCompetitor
                />
              )}
            </div>

            {/* Metric comparisons */}
            {data.our_candidate && data.competitor && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base text-white">
                    <Users className="h-4 w-4 text-violet-400" />
                    Comparação Direta
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
                    <span />
                    <div className="flex items-center gap-4">
                      <span className="text-blue-300">{CANDIDATE_B_DISPLAY}</span>
                      <span />
                      <span className="text-red-300">{COMPETITOR_DISPLAY}</span>
                      <span />
                    </div>
                  </div>
                  <MetricComparison
                    label="Engajamento Total"
                    ourValue={data.our_candidate.total_engagement}
                    theirValue={data.competitor.total_engagement}
                  />
                  <MetricComparison
                    label="Curtidas por Post"
                    ourValue={data.our_candidate.avg_likes_per_post}
                    theirValue={data.competitor.avg_likes_per_post}
                    format="decimal"
                  />
                  <MetricComparison
                    label="Comentários por Post"
                    ourValue={data.our_candidate.avg_comments_per_post}
                    theirValue={data.competitor.avg_comments_per_post}
                    format="decimal"
                  />
                  <MetricComparison
                    label="Sentimento Médio"
                    ourValue={data.our_candidate.average_sentiment_score}
                    theirValue={data.competitor.average_sentiment_score}
                    format="sentiment"
                  />
                  <MetricComparison
                    label="Total de Posts"
                    ourValue={data.our_candidate.total_posts}
                    theirValue={data.competitor.total_posts}
                  />
                  <MetricComparison
                    label="Total de Comentários"
                    ourValue={data.our_candidate.total_comments}
                    theirValue={data.competitor.total_comments}
                  />

                  {/* Summary badge */}
                  <div className="mt-4 rounded-lg border border-border/30 bg-secondary/10 p-3 text-center">
                    {data.engagement_advantage > 0 ? (
                      <p className="text-sm text-emerald-300">
                        {CANDIDATE_B_DISPLAY} tem <strong>{data.engagement_advantage.toFixed(0)}%</strong> mais engajamento por post
                      </p>
                    ) : data.engagement_advantage < 0 ? (
                      <p className="text-sm text-amber-300">
                        {COMPETITOR_DISPLAY} tem <strong>{Math.abs(data.engagement_advantage).toFixed(0)}%</strong> mais engajamento por post
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Engajamento similar entre as candidatas
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}

        {/* AI Competitive Strategy */}
        <div className="border-t border-border/30 pt-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-purple-600">
                <Brain className="h-5 w-5 text-white" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">
                  Estratégia Competitiva IA
                </h2>
                <p className="text-sm text-muted-foreground">
                  Recomendações para superar a concorrência
                </p>
              </div>
            </div>
            <Button
              onClick={handleGenerateStrategy}
              disabled={generating}
              className="bg-gradient-to-r from-red-600 to-orange-600 text-white hover:from-red-700 hover:to-orange-700 border-0 shadow-lg shadow-red-900/30"
            >
              {generating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analisando concorrência...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Gerar Contra-Estratégia
                </>
              )}
            </Button>
          </div>

          <div className="mt-4">
            {generating && (
              <div className="space-y-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <LoadingSkeleton key={i} variant="card" />
                ))}
              </div>
            )}

            {strategyError && !generating && (
              <ErrorMessage error={strategyError} onRetry={handleGenerateStrategy} />
            )}

            {/* Executive summary */}
            {strategyData?.resumo_executivo && !generating && (
              <Card className="mb-4 border-violet-800/30 bg-gradient-to-br from-violet-950/40 to-purple-950/30">
                <CardContent className="p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <Brain className="h-5 w-5 text-violet-400" />
                    <h3 className="text-sm font-semibold text-violet-300">
                      Análise Competitiva
                    </h3>
                  </div>
                  <p className="text-sm leading-relaxed text-foreground/80">
                    {strategyData.resumo_executivo}
                  </p>
                </CardContent>
              </Card>
            )}

            {sortedSuggestions.length > 0 && !generating && (
              <div className="space-y-4">
                {sortedSuggestions.map((suggestion, index) => (
                  <SuggestionCard
                    key={index}
                    suggestion={suggestion}
                    index={index}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
