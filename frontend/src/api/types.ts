export interface ModelProvider {
  id: string
  name: string
  provider_type: 'claude' | 'openai' | 'local'
  base_url?: string
  api_key?: string
  default_model?: string
  notes?: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface AIAgent {
  id: string
  name: string
  description?: string
  processor_type: 'claude' | 'openai' | 'local'
  model?: string
  prompt_template: string
  processor_config: Record<string, unknown>
  enabled: boolean
  provider_id?: string
  created_at: string
  updated_at: string
}

export interface PaginationMeta {
  total: number
  page: number
  limit: number
  pages: number
}

export interface ApiResponse<T> {
  success: boolean
  data: T
  error?: string
  meta?: PaginationMeta
}

export interface DataSource {
  id: string
  name: string
  description?: string
  channel_type: 'opencli' | 'web_scraper' | 'api' | 'rss' | 'cli'
  channel_config: Record<string, unknown>
  ai_config?: Record<string, unknown>
  enabled: boolean
  tags: string[]
  created_at: string
  updated_at: string
}

export interface CollectionTask {
  id: string
  source_id: string
  source_name?: string
  agent_id?: string
  trigger_type: string
  parameters: Record<string, unknown>
  priority: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  error_message?: string
  created_at: string
  updated_at: string
}

export interface TaskRun {
  id: string
  task_id: string
  status: string
  worker_id?: string
  celery_task_id?: string
  started_at?: string
  finished_at?: string
  duration_ms?: number
  records_collected: number
  error_message?: string
  created_at: string
}

export interface CollectedRecord {
  id: string
  task_id: string
  source_id: string
  raw_data: Record<string, unknown>
  normalized_data: Record<string, unknown>
  ai_enrichment?: Record<string, unknown>
  content_hash: string
  status: string
  error_message?: string
  created_at: string
  updated_at: string
}

export interface CronSchedule {
  id: string
  source_id: string
  agent_id?: string
  name: string
  cron_expression: string
  timezone: string
  parameters: Record<string, unknown>
  enabled: boolean
  is_one_time: boolean
  last_run_at?: string
  next_run_at?: string
  created_at: string
  updated_at: string
}

export interface NotificationRule {
  id: string
  name: string
  source_id?: string
  trigger_event: string
  notifier_type: string
  notifier_config: Record<string, unknown>
  filter_conditions?: Record<string, unknown>
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface NotificationLog {
  id: string
  rule_id: string
  record_id?: string
  status: string
  response_data?: Record<string, unknown>
  error_message?: string
  created_at: string
}

export interface ChromeEndpoint {
  url: string
  available: boolean
  novnc_port: number
  container_status?: string
  mode: 'bridge' | 'cdp'
  agent_url?: string | null
  agent_protocol?: 'http' | 'ws' | null
}

export interface BrowserBinding {
  id: string
  browser_endpoint: string
  site: string
  notes?: string
  created_at: string
  updated_at: string
}

export interface WorkerNode {
  id: string
  worker_id: string
  hostname: string
  status: string
  active_tasks: number
  last_heartbeat?: string
  created_at: string
  updated_at: string
}

export interface EdgeNode {
  id: string
  url: string
  label: string
  protocol: 'http' | 'ws'
  mode: 'bridge' | 'cdp'
  status: 'online' | 'offline'
  last_seen_at?: string | null
  ip?: string | null
  created_at: string
  updated_at: string
}

export interface EdgeNodeEvent {
  id: string
  node_id: string
  event: 'registered' | 'online' | 'offline'
  ip?: string | null
  event_meta?: Record<string, unknown> | null
  created_at: string
}

export interface SystemConfig {
  collection_mode: 'local' | 'agent'
  task_executor: 'local' | 'celery'
}

export interface NodeStats {
  total: number
  success: number
  failed: number
  success_rate: number
  records_collected: number
}

export interface DashboardStats {
  sources: { total: number; enabled: number; disabled: number }
  tasks: { total: number; running: number; failed: number }
  runs: { total: number; success: number; failed: number; success_rate: number }
  records: { total: number; ai_processed: number }
  recent_runs: Array<{
    id: string
    task_id: string
    task_trigger_type: string
    source_name: string
    status: string
    records_collected: number
    duration_ms?: number
    created_at: string
  }>
}
