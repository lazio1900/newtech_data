import apiClient from "./client"
import type { Complex, ComplexCreate } from "@/types/complex"

export const complexesApi = {
  list: (params?: { skip?: number; limit?: number; is_active?: boolean }) =>
    apiClient.get<Complex[]>("/api/complexes", { params }).then((r) => r.data),

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
      .post<{ message: string; task_id: string }>(
        "/api/complexes/discover-region",
        null,
        { params: { region_code: regionCode } }
      )
      .then((r) => r.data),
}
