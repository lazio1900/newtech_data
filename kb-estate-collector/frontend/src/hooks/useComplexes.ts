import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { complexesApi } from "@/api/complexes"
import type { ComplexCreate } from "@/types/complex"

export function useComplexes(params?: { is_active?: boolean; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ["complexes", params],
    queryFn: () => complexesApi.list(params),
  })
}

export function useComplex(id: number) {
  return useQuery({
    queryKey: ["complexes", id],
    queryFn: () => complexesApi.get(id),
    enabled: id > 0,
  })
}

export function useCreateComplex() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ComplexCreate) => complexesApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["complexes"] }),
  })
}

export function useUpdateComplex() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<ComplexCreate> }) =>
      complexesApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["complexes"] }),
  })
}

export function useDeleteComplex() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => complexesApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["complexes"] }),
  })
}

export function useDiscoverRegion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (regionCode: string) => complexesApi.discoverRegion(regionCode),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ["complexes"] }), 5000)
    },
  })
}
