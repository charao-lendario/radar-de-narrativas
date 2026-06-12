"use client"

import { fetchProfiles } from "@/lib/api"
import type { ProfileData } from "@/lib/types"
import { useApiData, type UseApiDataResult } from "@/hooks/use-api-data"

export function useProfiles(): UseApiDataResult<ProfileData[]> {
  return useApiData(() => fetchProfiles(), [])
}
