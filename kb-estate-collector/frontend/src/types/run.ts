export type RunStatus = "pending" | "running" | "success" | "partial" | "failed" | "cancelled"
export type TaskStatus = "pending" | "running" | "success" | "failed" | "retry" | "skipped"

export interface CrawlRun {
  id: number
  job_id: number | null
  status: RunStatus
  started_at: string | null
  finished_at: string | null
  total_tasks: number
  success_count: number
  failed_count: number
  skipped_count: number
  created_at: string
  target_summary?: string
}

export interface CrawlTask {
  id: number
  task_key: string
  status: TaskStatus
  started_at: string | null
  finished_at: string | null
  retry_count: number
  items_collected: number
  items_saved: number
  error_type: string | null
  error_message: string | null
}

export interface TargetComplex {
  id: number
  name: string
  address: string
  region_code: string | null
}

export interface CrawlRunDetail extends CrawlRun {
  tasks: CrawlTask[]
  target_complexes: TargetComplex[]
}
