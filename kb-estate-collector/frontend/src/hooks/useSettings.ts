import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { settingsApi } from "@/api/settings"

export function useSetting(key: string) {
  return useQuery({
    queryKey: ["settings", key],
    queryFn: () => settingsApi.get(key),
    refetchInterval: 15_000,
  })
}

export function useUpdateSetting(key: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (value: string) => settingsApi.update(key, value),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings", key] }),
  })
}
