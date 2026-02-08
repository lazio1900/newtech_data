export type ListingStatus = "active" | "sold" | "removed" | "unknown"

export interface KBPrice {
  id: number
  complex_id: number
  area_id: number
  as_of_date: string
  general_price: number | null
  high_avg_price: number | null
  low_avg_price: number | null
  fetched_at: string
}

export interface Transaction {
  id: number
  complex_id: number
  contract_date: string
  price: number
  exclusive_m2: number
  floor: number | null
  source: string
}

export interface Listing {
  id: number
  complex_id: number
  source_listing_id: string
  ask_price: number
  exclusive_m2: number | null
  floor: number | null
  status: ListingStatus
  fetched_at: string
}
