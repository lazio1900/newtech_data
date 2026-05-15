import apiClient from "./client"

export interface SystemSetting {
  key: string
  value: string
  description?: string | null
}

export const settingsApi = {
  get: (key: string) =>
    apiClient.get<SystemSetting>(`/api/settings/${key}`).then((r) => r.data),

  update: (key: string, value: string) =>
    apiClient
      .patch<SystemSetting>(`/api/settings/${key}`, { value })
      .then((r) => r.data),
}
