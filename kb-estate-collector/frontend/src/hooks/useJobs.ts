import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { jobsApi } from "@/api/jobs"
import type { JobCreate, JobUpdate } from "@/types/job"

export function useJobs(params?: { skip?: number; limit?: number; status_filter?: string }) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => jobsApi.list(params),
  })
}

export function useJob(id: number) {
  return useQuery({
    queryKey: ["jobs", id],
    queryFn: () => jobsApi.get(id),
    enabled: id > 0,
  })
}

export function useCreateJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: JobCreate) => jobsApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  })
}

export function useCreateAndRunJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: JobCreate) => jobsApi.createAndRun(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] })
      qc.invalidateQueries({ queryKey: ["runs"] })
    },
  })
}

export function useRunJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => jobsApi.run(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  })
}

export function usePauseJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => jobsApi.pause(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  })
}

export function useResumeJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => jobsApi.resume(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  })
}

export function useUpdateJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: JobUpdate }) =>
      jobsApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  })
}

export function useRunRegion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (regionCode: string) => jobsApi.runRegion(regionCode),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] })
      qc.invalidateQueries({ queryKey: ["runs"] })
      setTimeout(() => qc.invalidateQueries({ queryKey: ["complexes"] }), 5000)
    },
  })
}
