"use client"

import { useState } from "react"
import { useSearchParams } from "next/navigation"
import {
  ArrowUp,
  ArrowDown,
  ExternalLink,
  Brain,
  Loader2,
  ThumbsUp,
  ThumbsDown,
  Minus,
  X,
} from "lucide-react"
import { useOverview } from "@/hooks/use-overview"
import { fetchPosts, fetchContextualSentiment } from "@/lib/api"
import type { CandidateFilter } from "@/lib/constants"
import type { PostData, ContextualSentimentData } from "@/lib/types"
import { getCandidateId, formatDateMedium } from "@/lib/utils"
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { ErrorMessage } from "@/components/shared/error-message"
import { EmptyState } from "@/components/shared/empty-state"
import { SentimentBadge } from "@/components/dashboard/sentiment-badge"
import { useApiData } from "@/hooks/use-api-data"

type SortColumn =
  | "comment_count"
  | "like_count"
  | "positive_ratio"
  | "negative_ratio"
  | "sentiment_score"

const SORTABLE_COLUMNS: Array<{
  key: SortColumn
  label: string
}> = [
  { key: "like_count", label: "Curtidas" },
  { key: "comment_count", label: "Comentários" },
  { key: "positive_ratio", label: "% Positivo" },
  { key: "negative_ratio", label: "% Negativo" },
  { key: "sentiment_score", label: "Sentimento" },
]

const PAGE_SIZE = 20

function truncateCaption(caption: string, maxLength: number = 40): string {
  if (caption.length <= maxLength) return caption
  return caption.slice(0, maxLength).trim() + "..."
}

function ContextualBreakdown({
  data,
  onClose,
}: {
  data: ContextualSentimentData
  onClose: () => void
}) {
  return (
    <Card className="border-violet-800/30 bg-gradient-to-br from-violet-950/40 to-purple-950/30">
      <CardContent className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-violet-400" />
            <h3 className="text-sm font-semibold text-violet-300">
              Análise Contextual — {data.candidate_name}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="mb-4 text-xs italic text-muted-foreground">
          &ldquo;{data.caption_preview}...&rdquo;
        </p>

        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="rounded-lg bg-emerald-950/40 p-3">
            <div className="flex items-center justify-center gap-1.5">
              <ThumbsUp className="h-4 w-4 text-emerald-400" />
              <p className="text-2xl font-bold text-emerald-300">{data.apoio}</p>
            </div>
            <p className="mt-1 text-xs text-emerald-400/70">
              Apoio ({data.apoio_percent}%)
            </p>
          </div>
          <div className="rounded-lg bg-red-950/40 p-3">
            <div className="flex items-center justify-center gap-1.5">
              <ThumbsDown className="h-4 w-4 text-red-400" />
              <p className="text-2xl font-bold text-red-300">{data.contra}</p>
            </div>
            <p className="mt-1 text-xs text-red-400/70">
              Contra ({data.contra_percent}%)
            </p>
          </div>
          <div className="rounded-lg bg-slate-800/40 p-3">
            <div className="flex items-center justify-center gap-1.5">
              <Minus className="h-4 w-4 text-slate-400" />
              <p className="text-2xl font-bold text-slate-300">{data.neutro}</p>
            </div>
            <p className="mt-1 text-xs text-slate-400/70">
              Neutro ({data.neutro_percent}%)
            </p>
          </div>
        </div>

        {/* Stacked bar */}
        <div className="mt-4 flex h-3 overflow-hidden rounded-full">
          {data.apoio_percent > 0 && (
            <div
              className="bg-emerald-500"
              style={{ width: `${data.apoio_percent}%` }}
            />
          )}
          {data.neutro_percent > 0 && (
            <div
              className="bg-slate-500"
              style={{ width: `${data.neutro_percent}%` }}
            />
          )}
          {data.contra_percent > 0 && (
            <div
              className="bg-red-500"
              style={{ width: `${data.contra_percent}%` }}
            />
          )}
        </div>

        {/* Para onde aponta a emoção — separa crítica real de indignação com o tema */}
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-violet-300/80">
            Para onde aponta a emoção
          </p>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg border border-red-900/40 bg-red-950/30 p-3">
              <p className="text-xl font-bold text-red-300">{data.critica_candidato}</p>
              <p className="mt-1 text-[11px] leading-tight text-red-400/70">
                Crítica ao candidato ({data.critica_candidato_percent}%)
              </p>
            </div>
            <div className="rounded-lg border border-amber-900/40 bg-amber-950/30 p-3">
              <p className="text-xl font-bold text-amber-300">{data.indignacao_tema}</p>
              <p className="mt-1 text-[11px] leading-tight text-amber-400/70">
                Indignação com o tema ({data.indignacao_tema_percent}%)
              </p>
            </div>
            <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 p-3">
              <p className="text-xl font-bold text-slate-300">{data.ataque_terceiro}</p>
              <p className="mt-1 text-[11px] leading-tight text-slate-400/70">
                Ataque a terceiros ({data.ataque_terceiro_percent}%)
              </p>
            </div>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground/70">
            A indignação com o tema e o ataque a terceiros são engajamento — não contam como
            negatividade contra o candidato.
          </p>
        </div>

        <p className="mt-4 text-xs text-muted-foreground">
          {data.critica_candidato_percent > 25
            ? "Atenção: parcela relevante critica diretamente o candidato neste conteúdo."
            : data.indignacao_tema_percent > data.apoio_percent
              ? "A revolta aqui é com o TEMA do post, não com o candidato — sinal de engajamento forte e alinhado."
              : data.apoio_percent > 40
                ? "A maioria demonstra apoio ao candidato, inclusive quem expressa revolta com o tema abordado."
                : "Os comentários estão divididos — vale acompanhar a abordagem do conteúdo."}
        </p>
      </CardContent>
    </Card>
  )
}

export function PostsContent() {
  const searchParams = useSearchParams()
  const candidateFilter = (searchParams.get("candidate") ?? "charlles") as CandidateFilter

  const [sortColumn, setSortColumn] = useState<SortColumn>("comment_count")
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")
  const [extraPosts, setExtraPosts] = useState<PostData[]>([])
  const [loadingMore, setLoadingMore] = useState(false)
  const [currentOffset, setCurrentOffset] = useState(0)

  // Contextual sentiment state
  const [analyzingPostId, setAnalyzingPostId] = useState<string | null>(null)
  const [contextualData, setContextualData] = useState<Record<string, ContextualSentimentData>>({})
  const [contextualError, setContextualError] = useState<string | null>(null)

  const { data: overviewData } = useOverview()

  const candidateId =
    overviewData?.candidates
      ? getCandidateId(candidateFilter, overviewData.candidates)
      : undefined

  const { data, loading, error, refetch } = useApiData(
    () =>
      fetchPosts({
        candidate_id: candidateId,
        sort_by: sortColumn,
        order: sortOrder,
        limit: PAGE_SIZE,
        offset: 0,
      }),
    [candidateId, sortColumn, sortOrder]
  )

  const allPosts = data?.posts
    ? [...data.posts, ...extraPosts]
    : []

  const totalPosts = data?.total ?? 0

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))
    } else {
      setSortColumn(column)
      setSortOrder("desc")
    }
    setExtraPosts([])
    setCurrentOffset(0)
  }

  const handleLoadMore = async () => {
    const nextOffset = currentOffset + PAGE_SIZE
    setLoadingMore(true)
    try {
      const result = await fetchPosts({
        candidate_id: candidateId,
        sort_by: sortColumn,
        order: sortOrder,
        limit: PAGE_SIZE,
        offset: nextOffset,
      })
      setExtraPosts((prev) => [...prev, ...result.posts])
      setCurrentOffset(nextOffset)
    } catch {
      // Silently fail; user can retry
    } finally {
      setLoadingMore(false)
    }
  }

  const handleAnalyzeContext = async (postId: string) => {
    setAnalyzingPostId(postId)
    setContextualError(null)
    try {
      const result = await fetchContextualSentiment(postId)
      setContextualData((prev) => ({ ...prev, [postId]: result }))
    } catch (err) {
      setContextualError(
        err instanceof Error ? err.message : "Falha na análise contextual"
      )
    } finally {
      setAnalyzingPostId(null)
    }
  }

  const handleCloseContextual = (postId: string) => {
    setContextualData((prev) => {
      const next = { ...prev }
      delete next[postId]
      return next
    })
  }

  const showLoadMore = allPosts.length < totalPosts && allPosts.length > 0

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-white">Desempenho de Posts</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Qual conteúdo funciona melhor — clique na legenda para abrir o post no Instagram.
      </p>

      <div className="mt-6">
        {loading && allPosts.length === 0 && (
          <LoadingSkeleton variant="table" />
        )}

        {error && <ErrorMessage error={error} onRetry={refetch} />}

        {!loading && !error && allPosts.length === 0 && (
          <EmptyState message="Nenhum post encontrado." />
        )}

        {allPosts.length > 0 && (
          <>
            <div className="overflow-x-auto rounded-lg border border-border">
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-secondary/30">
                    <TableHead className="w-[100px]">Data</TableHead>
                    <TableHead className="min-w-[120px]">Legenda</TableHead>
                    {SORTABLE_COLUMNS.map((col) => (
                      <TableHead
                        key={col.key}
                        className="cursor-pointer select-none whitespace-nowrap"
                        onClick={() => handleSort(col.key)}
                      >
                        <span className="flex items-center gap-1">
                          {col.label}
                          {sortColumn === col.key && (
                            sortOrder === "desc" ? (
                              <ArrowDown className="h-3.5 w-3.5" />
                            ) : (
                              <ArrowUp className="h-3.5 w-3.5" />
                            )
                          )}
                        </span>
                      </TableHead>
                    ))}
                    <TableHead className="w-[100px]">Contexto</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allPosts.map((post) => (
                    <TableRow key={post.post_id} className="border-border hover:bg-secondary/20">
                      <TableCell className="whitespace-nowrap text-xs">
                        {formatDateMedium(post.posted_at)}
                      </TableCell>
                      <TableCell className="max-w-[180px]">
                        {post.url ? (
                          <a
                            href={post.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group flex items-center gap-1 text-blue-400 hover:text-blue-300"
                            title={post.caption}
                          >
                            <span className="truncate text-sm">
                              {truncateCaption(post.caption)}
                            </span>
                            <ExternalLink className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-100" />
                          </a>
                        ) : (
                          <span className="text-sm" title={post.caption}>
                            {truncateCaption(post.caption)}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>{post.like_count.toLocaleString("pt-BR")}</TableCell>
                      <TableCell>{post.comment_count}</TableCell>
                      <TableCell>
                        {(post.positive_ratio * 100).toFixed(0)}%
                      </TableCell>
                      <TableCell>
                        {(post.negative_ratio * 100).toFixed(0)}%
                      </TableCell>
                      <TableCell>
                        <SentimentBadge score={post.average_sentiment_score} />
                      </TableCell>
                      <TableCell>
                        {contextualData[post.post_id] ? (
                          <span className="text-xs text-emerald-400">
                            {contextualData[post.post_id].apoio_percent}% apoio
                          </span>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 gap-1 px-2 text-xs text-violet-400 hover:text-violet-300 hover:bg-violet-900/30"
                            onClick={() => handleAnalyzeContext(post.post_id)}
                            disabled={analyzingPostId === post.post_id}
                          >
                            {analyzingPostId === post.post_id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Brain className="h-3 w-3" />
                            )}
                            Analisar
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Contextual sentiment results */}
            {Object.entries(contextualData).length > 0 && (
              <div className="mt-6 space-y-4">
                {Object.entries(contextualData).map(([postId, cData]) => (
                  <ContextualBreakdown
                    key={postId}
                    data={cData}
                    onClose={() => handleCloseContextual(postId)}
                  />
                ))}
              </div>
            )}

            {contextualError && (
              <div className="mt-4 rounded-lg border border-red-800/30 bg-red-950/20 p-3 text-sm text-red-300">
                {contextualError}
              </div>
            )}

            {showLoadMore && (
              <div className="mt-4 flex justify-center">
                <Button
                  variant="outline"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="border-border/50 bg-secondary/50 text-foreground hover:bg-secondary"
                >
                  {loadingMore ? "Carregando..." : "Carregar mais"}
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
