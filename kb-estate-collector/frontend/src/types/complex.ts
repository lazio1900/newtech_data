export type PriorityLevel = "high" | "normal" | "low"

export interface Area {
  id: number
  exclusive_m2: number
  supply_m2: number | null
  pyeong: number | null
  kb_area_code: string | null
}

export interface Complex {
  id: number
  name: string
  address: string
  road_address: string | null
  region_code: string | null
  kb_complex_id: string | null
  priority: PriorityLevel
  is_active: boolean
  collect_listings: boolean
  total_households: number | null
  total_buildings: number | null
  max_floor: number | null
  built_year: string | null
  total_parking: number | null
  hallway_type: string | null
  heating_type: string | null
  builder: string | null
  areas: Area[]
}

export interface ComplexCreate {
  name: string
  address: string
  region_code?: string
  kb_complex_id?: string
  priority?: PriorityLevel
  is_active?: boolean
  collect_listings?: boolean
}

export interface ComplexLastRun {
  run_id: number
  status: string
  started_at: string | null
  finished_at: string | null
}

export type ComplexLastRunMap = Record<number, ComplexLastRun>

export interface PaginatedComplexes {
  items: Complex[]
  total: number
}

export interface RegionCounts {
  sido_counts: Record<string, number>
  region_counts: Record<string, number>
}

export interface Facility {
  id: number
  facility_type: string
  sub_type: string | null
  name: string
  address: string | null
  phone: string | null
  distance_m: number | null
  lat: number | null
  lng: number | null
  fetched_at: string | null
}

export interface FacilityGroup {
  counts: Record<string, number>
  items: Record<string, Facility[]>
}
