export type JobType = "KB_PRICE" | "KB_LISTING" | "KB_TRANSACTION" | "MOLIT_TRANSACTION"
export type JobStatus = "ACTIVE" | "PAUSED" | "DISABLED"

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
