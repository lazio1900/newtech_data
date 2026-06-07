import apiClient from "./client"
import type { Batch, SigunguBatch, DongBatch } from "@/types/batch"
import type { WeeklySchedule } from "@/types/schedule"

export const batchesApi = {
  list: () =>
    apiClient.get<Batch[]>("/api/batches").then((r) => r.data),

  getSchedule: () =>
    apiClient.get<WeeklySchedule>("/api/batches/schedule").then((r) => r.data),

  listSigungu: (sidoCode: string) =>
    apiClient.get<SigunguBatch[]>("/api/batches/sigungu", { params: { sido_code: sidoCode } })
      .then((r) => r.data),

  listDong: (regionCode: string) =>
    apiClient.get<DongBatch[]>("/api/batches/dong", { params: { region_code: regionCode } })
      .then((r) => r.data),

  run: (sidoCode: string) =>
    apiClient
      .post<{ message: string; run_id: number; task_id: string; complex_count: number }>(
        `/api/batches/${sidoCode}/run`,
      )
      .then((r) => r.data),

  runScoped: (scope: "sigungu" | "dong", code: string) =>
    apiClient
      .post<{ message: string; run_id: number; task_id: string; complex_count: number }>(
        `/api/batches/scoped/run`, { scope, code },
      )
      .then((r) => r.data),

  updateSchedule: (sidoCode: string, cronSchedule: string | null) =>
    apiClient
      .patch<{ message: string; sido_code: string; cron_schedule: string | null }>(
        `/api/batches/${sidoCode}/schedule`,
        { cron_schedule: cronSchedule },
      )
      .then((r) => r.data),

  updateScopedSchedule: (scope: "sigungu" | "dong", code: string, cronSchedule: string | null) =>
    apiClient
      .patch<{ message: string; scope: string; code: string; cron_schedule: string | null }>(
        `/api/batches/scoped/schedule`,
        { scope, code, cron_schedule: cronSchedule },
      )
      .then((r) => r.data),
}
