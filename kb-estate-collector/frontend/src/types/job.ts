export type JobType = "kb_price" | "region_all"
export type JobStatus = "active" | "paused" | "disabled"

export interface CrawlJob {
  id: number
  name: string
  job_type: JobType
  description: string | null
  status: JobStatus
  target_config: string | null
  cron_schedule: string | null
  max_concurrency: number
  rate_limit_per_minute: number
  created_at: string
  updated_at: string
  last_run_id: number | null
  last_run_status: string | null
  last_run_at: string | null
}

export interface JobCreate {
  name: string
  job_type: JobType
  description?: string
  target_config?: string
  cron_schedule?: string
  max_concurrency?: number
  rate_limit_per_minute?: number
}

export interface JobUpdate {
  name?: string
  description?: string
  cron_schedule?: string
  target_config?: string
}
