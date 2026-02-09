import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { batchesApi } from "@/api/batches"

export function useBatches() {
  return useQuery({
    queryKey: ["batches"],
    queryFn: () => batchesApi.list(),
    refetchInterval: 10_000,
  })
}

export function useRunBatch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sidoCode: string) => batchesApi.run(sidoCode),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["batches"] })
      qc.invalidateQueries({ queryKey: ["runs"] })
    },
  })
}

export function useUpdateBatchSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ sidoCode, cronSchedule }: { sidoCode: string; cronSchedule: string | null }) =>
      batchesApi.updateSchedule(sidoCode, cronSchedule),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["batches"] }),
  })
}
