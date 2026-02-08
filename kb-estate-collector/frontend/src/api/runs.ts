import apiClient from "./client"
import type { CrawlRun, CrawlRunDetail, CrawlTask } from "@/types/run"

export const runsApi = {
  list: (params?: {
    skip?: number
    limit?: number
    job_id?: number
    status_filter?: string
  }) =>
    apiClient.get<CrawlRun[]>("/api/runs", { params }).then((r) => r.data),

  get: (id: number) =>
    apiClient.get<CrawlRunDetail>(`/api/runs/${id}`).then((r) => r.data),

  tasks: (
    runId: number,
    params?: { skip?: number; limit?: number; status_filter?: string }
  ) =>
    apiClient
      .get<CrawlTask[]>(`/api/runs/${runId}/tasks`, { params })
      .then((r) => r.data),
}
