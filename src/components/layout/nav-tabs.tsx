"use client"

import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import { cn } from "@/lib/utils"
import { NAV_TABS } from "@/lib/constants"
import type { CandidateFilter } from "@/lib/constants"

export function NavTabs() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const candidateFilter = (searchParams.get("candidate") ?? "charlles") as CandidateFilter

  return (
    <nav className="border-b bg-background">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="-mb-px flex space-x-1 overflow-x-auto scrollbar-none">
          {NAV_TABS.filter((tab) => {
            if (tab.href === "/competitor" && candidateFilter === "charlles") return false
            return true
          }).map((tab) => {
            const isActive =
              pathname === tab.href ||
              (tab.href === "/overview" && pathname === "/")

            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  "whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition-colors",
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
                )}
              >
                {tab.label}
              </Link>
            )
          })}
        </div>
      </div>
    </nav>
  )
}
