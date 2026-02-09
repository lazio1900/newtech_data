export interface BatchRun {
  id: number
  status: string
  started_at: string | null
  finished_at: string | null
  total_tasks: number
  success_count: number
  failed_count: number
  skipped_count: number
}

export interface Batch {
  sido_code: string
  sido_name: string
  complex_count: number
  job_id: number | null
  job_status: string | null
  cron_schedule: string | null
  last_runs: BatchRun[]
}
