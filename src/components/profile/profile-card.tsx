"use client"

import { useState } from "react"
import { BadgeCheck, ExternalLink, Users, UserPlus, Images } from "lucide-react"
import type { ProfileData } from "@/lib/types"
import { avatarUrl } from "@/lib/api"
import { cn, formatCompact, formatNumber, formatDelta, formatRelative } from "@/lib/utils"

const ACCENTS: Record<string, { color: string; soft: string }> = {
  charlles: { color: "#60a5fa", soft: "rgba(96,165,250,0.14)" },
  sheila: { color: "#fb7185", soft: "rgba(251,113,133,0.14)" },
  ione: { color: "#fbbf24", soft: "rgba(251,191,36,0.14)" },
}

interface ProfileCardProps {
  profile: ProfileData
  highlighted?: boolean
  className?: string
}

export function ProfileCard({ profile, highlighted, className }: ProfileCardProps) {
  const accent = ACCENTS[profile.candidate_id] ?? ACCENTS.charlles
  const [imgError, setImgError] = useState(false)
  const initials = (profile.full_name || profile.display_name)
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
  const delta = formatDelta(profile.followers_delta)

  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-2xl border bg-card transition-all duration-300 hover:shadow-lg",
        highlighted ? "border-transparent ring-2" : "border-border/60",
        className
      )}
      style={
        highlighted
          ? ({ "--tw-ring-color": accent.color } as React.CSSProperties)
          : undefined
      }
    >
      {/* glow superior na cor do candidato */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-28"
        style={{ background: `linear-gradient(180deg, ${accent.soft}, transparent)` }}
      />

      <div className="relative p-5">
        {/* Cabeçalho: avatar + identidade */}
        <div className="flex items-start gap-4">
          <div className="relative shrink-0">
            <div
              className="h-[76px] w-[76px] overflow-hidden rounded-full ring-2 ring-offset-2 ring-offset-card"
              style={{ ["--tw-ring-color" as string]: accent.color }}
            >
              {profile.has_avatar && !imgError ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={avatarUrl(profile.candidate_id)}
                  alt={profile.display_name}
                  width={76}
                  height={76}
                  className="h-full w-full object-cover"
                  onError={() => setImgError(true)}
                />
              ) : (
                <div
                  className="flex h-full w-full items-center justify-center text-xl font-bold text-white"
                  style={{ background: accent.soft }}
                >
                  {initials}
                </div>
              )}
            </div>
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <h3 className="truncate text-base font-bold text-white">
                {profile.full_name || profile.display_name}
              </h3>
              {profile.verified && (
                <BadgeCheck
                  className="h-4 w-4 shrink-0"
                  style={{ color: accent.color }}
                  aria-label="Verificado"
                />
              )}
            </div>
            <a
              href={`https://www.instagram.com/${profile.username}/`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              @{profile.username}
              <ExternalLink className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-60" />
            </a>
            {profile.cargo && (
              <div className="mt-1.5">
                <span
                  className="inline-block rounded-full px-2 py-0.5 text-[11px] font-medium"
                  style={{ background: accent.soft, color: accent.color }}
                >
                  {profile.cargo}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Bio */}
        {profile.biography && (
          <p className="mt-4 line-clamp-3 whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
            {profile.biography}
          </p>
        )}

        {/* Estatísticas */}
        <div className="mt-4 grid grid-cols-3 divide-x divide-border/50 rounded-xl bg-secondary/40 py-3">
          <Stat
            icon={<Users className="h-3.5 w-3.5" />}
            value={formatCompact(profile.followers_count)}
            title={formatNumber(profile.followers_count)}
            label="Seguidores"
            badge={delta}
            badgeColor={profile.followers_delta && profile.followers_delta > 0 ? "#34d399" : "#fb7185"}
          />
          <Stat
            icon={<UserPlus className="h-3.5 w-3.5" />}
            value={formatCompact(profile.follows_count)}
            title={formatNumber(profile.follows_count)}
            label="Seguindo"
          />
          <Stat
            icon={<Images className="h-3.5 w-3.5" />}
            value={formatCompact(profile.posts_count)}
            title={formatNumber(profile.posts_count)}
            label="Posts"
          />
        </div>

        {/* Rodapé */}
        <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground/70">
          <span className="truncate">{profile.category ?? "Instagram"}</span>
          <span className="shrink-0">Atualizado {formatRelative(profile.updated_at)}</span>
        </div>
      </div>
    </div>
  )
}

function Stat({
  icon,
  value,
  title,
  label,
  badge,
  badgeColor,
}: {
  icon: React.ReactNode
  value: string
  title: string
  label: string
  badge?: string | null
  badgeColor?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center px-1" title={title}>
      <div className="flex items-center gap-1">
        <span className="text-lg font-bold text-white">{value}</span>
        {badge && (
          <span className="text-[10px] font-semibold" style={{ color: badgeColor }}>
            {badge}
          </span>
        )}
      </div>
      <div className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
        <span className="opacity-60">{icon}</span>
        {label}
      </div>
    </div>
  )
}
