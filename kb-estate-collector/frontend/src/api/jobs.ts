import apiClient from "./client"
import type { CrawlJob, JobCreate, JobUpdate } from "@/types/job"

export const jobsApi = {
  list: (params?: { skip?: number; limit?: number; status_filter?: string }) =>
    apiClient.get<CrawlJob[]>("/api/jobs", { params }).then((r) => r.data),

  get: (id: number) =>
    apiClient.get<CrawlJob>(`/api/jobs/${id}`).then((r) => r.data),

  create: (data: JobCreate) =>
    apiClient.post<CrawlJob>("/api/jobs", data).then((r) => r.data),

  createAndRun: (data: JobCreate) =>
    apiClient
      .post<{ message: string; job_id: number; run_id: number; task_id: string }>(
        "/api/jobs/create-and-run",
        data,
      )
      .then((r) => r.data),

  run: (id: number) =>
    apiClient
      .post<{ message: string; job_id: number; run_id: number; task_id: string }>(
        `/api/jobs/${id}/run`
      )
      .then((r) => r.data),

  pause: (id: number) =>
    apiClient
      .patch<{ message: string; job_id: number }>(`/api/jobs/${id}/pause`)
      .then((r) => r.data),

  resume: (id: number) =>
    apiClient
      .patch<{ message: string; job_id: number }>(`/api/jobs/${id}/resume`)
      .then((r) => r.data),

  update: (id: number, data: JobUpdate) =>
    apiClient.patch<CrawlJob>(`/api/jobs/${id}`, data).then((r) => r.data),

  runRegion: (regionCode: string, jobId?: number) =>
    apiClient
      .post<{ message: string; run_id: number; task_id: string }>("/api/jobs/run-region", null, {
        params: { region_code: regionCode, job_id: jobId },
      })
      .then((r) => r.data),
}
