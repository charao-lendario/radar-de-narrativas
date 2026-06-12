"use client"

import { useState } from "react"
import { useSearchParams } from "next/navigation"
import { RefreshCw, Loader2 } from "lucide-react"
import { useOverview } from "@/hooks/use-overview"
import { useProfiles } from "@/hooks/use-profiles"
import { triggerScraping } from "@/lib/api"
import type { CandidateFilter } from "@/lib/constants"
import { CANDIDATE_A_USERNAME, CANDIDATE_B_USERNAME } from "@/lib/constants"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { ErrorMessage } from "@/components/shared/error-message"
import { EmptyState } from "@/components/shared/empty-state"
import { SummaryRow } from "@/components/dashboard/summary-row"
import { MetricCard } from "@/components/dashboard/metric-card"
import { ProfileCard } from "@/components/profile/profile-card"
import { Button } from "@/components/ui/button"

function PageHeader({
  subtitle,
  onRefresh,
  refreshing,
  message,
}: {
  subtitle?: string
  onRefresh?: () => void
  refreshing?: boolean
  message?: string | null
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Painel de Campanha</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {onRefresh && (
        <div className="flex items-center gap-3">
          {message && <span className="text-xs text-muted-foreground">{message}</span>}
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={refreshing}
            className="gap-2 border-border/50 bg-secondary/50 text-foreground hover:bg-secondary"
          >
            {refreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {refreshing ? "Coletando…" : "Atualizar dados"}
          </Button>
        </div>
      )}
    </div>
  )
}

export function OverviewContent() {
  const searchParams = useSearchParams()
  const candidateFilter = (searchParams.get("candidate") ?? "charlles") as CandidateFilter
  const { data, loading, error, refetch } = useOverview()
  const { data: profiles } = useProfiles()

  const [triggering, setTriggering] = useState(false)
  const [triggerMessage, setTriggerMessage] = useState<string | null>(null)

  const handleTriggerScraping = async () => {
    setTriggering(true)
    setTriggerMessage(null)
    try {
      await triggerScraping()
      setTriggerMessage("Coleta iniciada!")
    } catch (err) {
      setTriggerMessage(
        err instanceof Error && err.message.includes("409")
          ? "Coleta já em andamento."
          : "Erro ao iniciar coleta."
      )
    } finally {
      setTriggering(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader subtitle="Carregando dados…" />
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <LoadingSkeleton variant="card" />
          <LoadingSkeleton variant="card" />
        </div>
        <LoadingSkeleton variant="card" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader />
        <ErrorMessage error={error} onRetry={refetch} />
      </div>
    )
  }

  if (!data || data.candidates.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader />
        <EmptyState
          message="Nenhum dado disponível. Inicie uma coleta de dados."
          actionLabel={triggering ? undefined : "Iniciar coleta"}
          onAction={triggering ? undefined : handleTriggerScraping}
        />
      </div>
    )
  }

  const selectedUsername =
    candidateFilter === "charlles" ? CANDIDATE_A_USERNAME : CANDIDATE_B_USERNAME
  const candidate = data.candidates.find((c) => c.username === selectedUsername)
  const monitored = (profiles ?? []).filter((p) => !p.is_competitor)

  return (
    <div className="space-y-8">
      <PageHeader
        subtitle="Perfis monitorados e inteligência de sentimento em tempo real no Instagram."
        onRefresh={handleTriggerScraping}
        refreshing={triggering}
        message={triggerMessage}
      />

      {/* Perfis vivos */}
      {monitored.length > 0 && (
        <section>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Perfis monitorados
          </h2>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {monitored.map((p) => (
              <ProfileCard
                key={p.candidate_id}
                profile={p}
                highlighted={p.username === selectedUsername}
              />
            ))}
          </div>
        </section>
      )}

      {/* Métricas do candidato selecionado */}
      {candidate && (
        <section className="space-y-5">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Análise de sentimento — {candidate.display_name}
          </h2>
          <SummaryRow
            totalComments={candidate.total_comments}
            averageSentiment={candidate.average_sentiment_score}
            lastScrape={data.last_scrape}
          />
          <MetricCard candidate={candidate} />
        </section>
      )}
    </div>
  )
}
