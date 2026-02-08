import apiClient from "./client"
import type { KBPrice, Transaction, Listing } from "@/types/data"

export const dataApi = {
  kbPrices: (params?: {
    complex_id?: number
    area_id?: number
    from_date?: string
    to_date?: string
    skip?: number
    limit?: number
  }) =>
    apiClient.get<KBPrice[]>("/api/data/kb-prices", { params }).then((r) => r.data),

  transactions: (params?: {
    complex_id?: number
    from_date?: string
    to_date?: string
    skip?: number
    limit?: number
  }) =>
    apiClient
      .get<Transaction[]>("/api/data/transactions", { params })
      .then((r) => r.data),

  listings: (params?: {
    complex_id?: number
    status?: string
    skip?: number
    limit?: number
  }) =>
    apiClient
      .get<Listing[]>("/api/data/listings", { params })
      .then((r) => r.data),

  exportPricesCsv: (params?: {
    complex_id?: number
    area_id?: number
    from_date?: string
    to_date?: string
  }) => {
    const query = new URLSearchParams()
    if (params?.complex_id) query.set("complex_id", String(params.complex_id))
    if (params?.area_id) query.set("area_id", String(params.area_id))
    if (params?.from_date) query.set("from_date", params.from_date)
    if (params?.to_date) query.set("to_date", params.to_date)
    const url = `/api/data/kb-prices/export?${query.toString()}`
    window.open(url, "_blank")
  },
}
