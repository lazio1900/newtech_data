export interface ScheduleRow {
  job_id: number
  name: string
  dow: number
  hour: number
  minute: number
  dow_name: string
  kind: string
  summary: string
  complexes: number
  dur_hours: number
  dur_source: string
  end_dow_name: string
  end_hour: number
  end_minute: number
  crosses_day: boolean
}

export interface ScheduleClash {
  job_id: number
  name: string
  dur_hours: number
  next_job_id: number
  next_name: string
  overlap_hours: number
}

export interface ChunkCode {
  region_code: string
  name: string
  complexes: number
}

export interface ChunkDetail {
  job_id: number
  name: string
  dow_name: string | null
  hour: number | null
  minute: number | null
  complexes: number
  dur_hours: number
  dur_source: string
  codes: ChunkCode[]
}

export interface CoverageRow {
  sido: string
  sido_name: string
  chunk_codes: number
  db_codes: number
  ok: boolean
  overlaps: string[]
  missing: string[]
  empty: string[]
}

export interface PausedJob {
  job_id: number
  name: string
  summary: string
  complexes: number
}

export interface WeeklySchedule {
  schedule: ScheduleRow[]
  clashes: ScheduleClash[]
  chunks: ChunkDetail[]
  coverage: CoverageRow[]
  paused: PausedJob[]
}
