import apiClient from "./client"
import type { Complex, ComplexCreate, ComplexLastRunMap, PaginatedComplexes, RegionCounts } from "@/types/complex"

export const complexesApi = {
  list: (params?: { skip?: number; limit?: number; is_active?: boolean; search?: string; region_code?: string }) =>
    apiClient.get<PaginatedComplexes>("/api/complexes", { params }).then((r) => r.data),

  regionCounts: () =>
    apiClient.get<RegionCounts>("/api/complexes/region-counts").then((r) => r.data),

  get: (id: number) =>
    apiClient.get<Complex>(`/api/complexes/${id}`).then((r) => r.data),

  create: (data: ComplexCreate) =>
    apiClient.post<Complex>("/api/complexes", data).then((r) => r.data),

  update: (id: number, data: Partial<ComplexCreate>) =>
    apiClient.patch<Complex>(`/api/complexes/${id}`, data).then((r) => r.data),

  delete: (id: number) =>
    apiClient.delete(`/api/complexes/${id}`).then((r) => r.data),

  discoverRegion: (regionCode: string) =>
    apiClient
      .post<{
        region_code: string
        total_found: number
        new_registered: number
        already_exists: number
      }>("/api/complexes/discover-region", null, {
        params: { region_code: regionCode },
      })
      .then((r) => r.data),

  collect: (id: number) =>
    apiClient
      .post<{ message: string; run_id: number; task_id: string }>(
        `/api/complexes/${id}/collect`,
      )
      .then((r) => r.data),

  batchCollect: (complexIds: number[]) =>
    apiClient
      .post<{ message: string; run_id: number; task_id: string; count: number }>(
        "/api/complexes/batch-collect",
        { complex_ids: complexIds },
      )
      .then((r) => r.data),

  getLastRuns: () =>
    apiClient
      .get<ComplexLastRunMap>("/api/complexes/last-runs")
      .then((r) => r.data),
}
