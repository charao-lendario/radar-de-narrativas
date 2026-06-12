"use client"

import { useEffect, useRef, useState } from "react"
import { Loader2, Link2, Sparkles, TrendingUp, TrendingDown, Minus } from "lucide-react"
import { startCompare, fetchCompareStatus } from "@/lib/api"
import type { CompareResult, CompetitiveAnalysisData } from "@/lib/types"
import { ProfileCard } from "@/components/profile/profile-card"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { formatCompact } from "@/lib/utils"

const POLL_MS = 6000
const MAX_POLLS = 40 // ~4 min

export function ComparePanel({ ourId = "sheila" }: { ourId?: string }) {
  const [url, setUrl] = useState("")
  const [result, setResult] = useState<CompareResult | null>(null)
  const [phase, setPhase] = useState<"idle" | "running" | "ready" | "error">("idle")
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollsRef = useRef(0)

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const stopPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim() || phase === "running") return
    setErrorMsg(null)
    setResult(null)
    setPhase("running")
    pollsRef.current = 0
    try {
      const started = await startCompare(url.trim(), ourId)
      if (started.status === "not_found" || !started.username) {
        setPhase("error")
        setErrorMsg(started.message || "Não consegui identificar um perfil válido nesse link.")
        return
      }
      setResult(started)
      const username = started.username
      stopPolling()
      pollRef.current = setInterval(async () => {
        pollsRef.current += 1
        try {
          const status = await fetchCompareStatus(username, ourId)
          setResult(status)
          if (status.status === "ready") {
            stopPolling()
            setPhase("ready")
          } else if (pollsRef.current >= MAX_POLLS) {
            stopPolling()
            setPhase("error")
            setErrorMsg("A análise está demorando mais que o esperado. Tente novamente em instantes.")
          }
        } catch {
          // mantém tentando até o limite
        }
      }, POLL_MS)
    } catch {
      setPhase("error")
      setErrorMsg("Erro ao iniciar a comparação. Verifique o link e tente de novo.")
    }
  }

  return (
    <Card className="border-border/60 bg-gradient-to-br from-card to-secondary/20">
      <CardContent className="p-5">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600">
            <Link2 className="h-4 w-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">Comparar com outro perfil</h3>
            <p className="text-xs text-muted-foreground">
              Cole o link de qualquer perfil do Instagram e compare na hora.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-2 sm:flex-row">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="instagram.com/perfil  ou  @perfil"
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-primary/60 focus:ring-1 focus:ring-primary/40"
          />
          <Button
            type="submit"
            disabled={phase === "running" || !url.trim()}
            className="gap-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white hover:from-violet-700 hover:to-fuchsia-700"
          >
            {phase === "running" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {phase === "running" ? "Analisando…" : "Comparar"}
          </Button>
        </form>

        {/* Estado de análise / erro */}
        {phase === "running" && (
          <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {result?.message || "Coletando perfil, posts e comentários…"} Isso leva ~1-2 min.
          </div>
        )}
        {phase === "error" && errorMsg && (
          <p className="mt-3 text-xs text-red-300">{errorMsg}</p>
        )}

        {/* Resultado */}
        {result?.our_profile && result?.competitor_profile && (
          <div className="mt-5 space-y-5">
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <ProfileCard profile={result.our_profile} highlighted />
              <ProfileCard profile={result.competitor_profile} />
            </div>
            {result.analysis && (
              <CompareMetrics
                analysis={result.analysis}
                ourName={result.our_profile.display_name}
                theirName={result.competitor_profile.display_name}
              />
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function Row({
  label,
  our,
  their,
  fmt = (v: number) => v.toLocaleString("pt-BR"),
}: {
  label: string
  our: number
  their: number
  fmt?: (v: number) => string
}) {
  const diff = our - their
  const tied = Math.abs(diff) < 0.01
  return (
    <div className="flex items-center justify-between rounded-lg border border-border/30 bg-secondary/20 px-3 py-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-rose-300">{fmt(our)}</span>
        <span className="text-[10px] text-muted-foreground/50">vs</span>
        <span className="text-sm font-semibold text-amber-300">{fmt(their)}</span>
        {tied ? (
          <Minus className="h-3.5 w-3.5 text-muted-foreground" />
        ) : diff > 0 ? (
          <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
        ) : (
          <TrendingDown className="h-3.5 w-3.5 text-red-400" />
        )}
      </div>
    </div>
  )
}

function CompareMetrics({
  analysis,
  ourName,
  theirName,
}: {
  analysis: CompetitiveAnalysisData
  ourName: string
  theirName: string
}) {
  const our = analysis.our_candidate
  const their = analysis.competitor
  if (!our || !their) return null
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-end gap-3 px-3 text-[11px]">
        <span className="text-rose-300">{ourName}</span>
        <span className="text-muted-foreground/40">vs</span>
        <span className="text-amber-300">{theirName}</span>
        <span className="w-3.5" />
      </div>
      <Row label="Engajamento total" our={our.total_engagement} their={their.total_engagement} fmt={formatCompact} />
      <Row label="Curtidas por post" our={our.avg_likes_per_post} their={their.avg_likes_per_post} fmt={(v) => formatCompact(Math.round(v))} />
      <Row label="Comentários por post" our={our.avg_comments_per_post} their={their.avg_comments_per_post} fmt={(v) => v.toFixed(0)} />
      <Row label="Sentimento médio" our={our.average_sentiment_score} their={their.average_sentiment_score} fmt={(v) => v.toFixed(2)} />
    </div>
  )
}
