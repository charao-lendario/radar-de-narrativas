import { Suspense } from "react"
import Link from "next/link"
import { CandidateFilter } from "@/components/layout/candidate-filter"

export function Header() {
  return (
    <header className="border-b border-border/40 bg-[#0a0b0f]">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/overview" aria-label="Radar de Narrativas" className="shrink-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.png"
            alt="Radar de Narrativas"
            className="h-14 w-auto select-none sm:h-16"
            draggable={false}
          />
        </Link>
        <Suspense fallback={null}>
          <CandidateFilter />
        </Suspense>
      </div>
    </header>
  )
}
