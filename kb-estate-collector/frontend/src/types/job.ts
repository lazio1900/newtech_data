export type JobType = "kb_price" | "kb_listing" | "kb_transaction" | "molit_transaction" | "region_all"
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
