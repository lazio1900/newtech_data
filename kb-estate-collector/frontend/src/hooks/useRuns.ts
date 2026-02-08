import { useQuery } from "@tanstack/react-query"
import { runsApi } from "@/api/runs"

export function useRuns(params?: {
  skip?: number
  limit?: number
  job_id?: number
  status_filter?: string
}) {
  return useQuery({
    queryKey: ["runs", params],
    queryFn: () => runsApi.list(params),
  })
}

export function useRun(id: number) {
  return useQuery({
    queryKey: ["runs", id],
    queryFn: () => runsApi.get(id),
    enabled: id > 0,
  })
}

export function useRunTasks(
  runId: number,
  params?: { skip?: number; limit?: number; status_filter?: string }
) {
  return useQuery({
    queryKey: ["runs", runId, "tasks", params],
    queryFn: () => runsApi.tasks(runId, params),
    enabled: runId > 0,
  })
}
