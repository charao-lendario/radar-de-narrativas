"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { NAV_TABS } from "@/lib/constants"

export function NavTabs() {
  const pathname = usePathname()

  return (
    <nav className="sticky top-0 z-30 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="-mb-px flex space-x-1 overflow-x-auto scrollbar-none">
          {NAV_TABS.map((tab) => {
            const isActive =
              pathname === tab.href ||
              (tab.href === "/overview" && pathname === "/")

            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  "relative whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition-colors",
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
