import { useQuery } from "@tanstack/react-query"
import { runsApi } from "@/api/runs"
import type { RunStatus } from "@/types/run"

const ACTIVE_STATUSES: RunStatus[] = ["pending", "running"]

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
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status && ACTIVE_STATUSES.includes(status as RunStatus)) {
        return 3000 // 3초마다 갱신 (진행중일 때)
      }
      return false // 완료되면 갱신 중지
    },
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
    refetchInterval: (query) => {
      // 태스크 중 실행중인 것이 있으면 자동 갱신
      const tasks = query.state.data
      if (tasks?.some((t) => ACTIVE_STATUSES.includes(t.status as RunStatus))) {
        return 3000
      }
      return false
    },
  })
}
