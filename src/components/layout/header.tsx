import { Suspense } from "react"
import { CandidateFilter } from "@/components/layout/candidate-filter"

export function Header() {
  return (
    <header className="border-b border-border/50 bg-[#0a1220]">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <div>
          <h1 className="text-lg font-bold tracking-tight text-white sm:text-xl">
            Radar de Narrativas
          </h1>
          <p className="text-xs text-blue-300/70">
            Charlles Evangelista & Delegada Sheila
          </p>
        </div>
        <Suspense fallback={null}>
          <CandidateFilter />
        </Suspense>
      </div>
    </header>
  )
}
