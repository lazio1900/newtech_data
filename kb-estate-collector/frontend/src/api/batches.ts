import apiClient from "./client"
import type { Batch } from "@/types/batch"

export const batchesApi = {
  list: () =>
    apiClient.get<Batch[]>("/api/batches").then((r) => r.data),

  run: (sidoCode: string) =>
    apiClient
      .post<{ message: string; run_id: number; task_id: string; complex_count: number }>(
        `/api/batches/${sidoCode}/run`,
      )
      .then((r) => r.data),

  updateSchedule: (sidoCode: string, cronSchedule: string | null) =>
    apiClient
      .patch<{ message: string; sido_code: string; cron_schedule: string | null }>(
        `/api/batches/${sidoCode}/schedule`,
        { cron_schedule: cronSchedule },
      )
      .then((r) => r.data),
}
