import { apiClient } from './client'
import type {
  AIAgent,
  ApiResponse,
  ModelProvider,
  BrowserBinding,
  ChromeEndpoint,
  CollectedRecord,
  CollectionTask,
  CronSchedule,
  DataSource,
  DashboardStats,
  NotificationLog,
  NotificationRule,
  TaskRun,
  WorkerNode,
} from './types'

// ── Dashboard ──────────────────────────────────────────────────────────────────
export const getDashboardStats = () =>
  apiClient.get<ApiResponse<DashboardStats>>('/dashboard/stats').then((r) => r.data.data)

// ── Sources ────────────────────────────────────────────────────────────────────
export const listSources = (params?: { page?: number; limit?: number; enabled?: boolean }) =>
  apiClient.get<ApiResponse<DataSource[]>>('/sources', { params }).then((r) => r.data)

export const getSource = (id: string) =>
  apiClient.get<ApiResponse<DataSource>>(`/sources/${id}`).then((r) => r.data.data)

export const createSource = (data: Partial<DataSource>) =>
  apiClient.post<ApiResponse<DataSource>>('/sources', data).then((r) => r.data.data)

export const updateSource = (id: string, data: Partial<DataSource>) =>
  apiClient.patch<ApiResponse<DataSource>>(`/sources/${id}`, data).then((r) => r.data.data)

export const deleteSource = (id: string) =>
  apiClient.delete<ApiResponse<null>>(`/sources/${id}`).then((r) => r.data)

export const testSourceConnectivity = (id: string) =>
  apiClient
    .post<ApiResponse<{ connected: boolean; errors: string[] }>>(`/sources/${id}/test`)
    .then((r) => r.data.data)

// ── Tasks ──────────────────────────────────────────────────────────────────────
export const listTasks = (params?: {
  source_id?: string
  status?: string
  page?: number
  limit?: number
}) => apiClient.get<ApiResponse<CollectionTask[]>>('/tasks', { params }).then((r) => r.data)

export const triggerTask = (
  source_id: string,
  parameters?: Record<string, unknown>,
  agent_id?: string,
) =>
  apiClient
    .post<ApiResponse<{ task_id: string; celery_task_id: string }>>('/tasks/trigger', {
      source_id,
      parameters: parameters ?? {},
      ...(agent_id ? { agent_id } : {}),
    })
    .then((r) => r.data.data)

export const getTask = (id: string) =>
  apiClient.get<ApiResponse<CollectionTask>>(`/tasks/${id}`).then((r) => r.data.data)

export const listTaskRuns = (task_id: string) =>
  apiClient.get<ApiResponse<TaskRun[]>>(`/tasks/${task_id}/runs`).then((r) => r.data)

// ── Records ────────────────────────────────────────────────────────────────────
export const listRecords = (params?: {
  source_id?: string
  task_id?: string
  status?: string
  page?: number
  limit?: number
}) => apiClient.get<ApiResponse<CollectedRecord[]>>('/records', { params }).then((r) => r.data)

export const getRecord = (id: string) =>
  apiClient.get<ApiResponse<CollectedRecord>>(`/records/${id}`).then((r) => r.data.data)

export const deleteRecord = (id: string) =>
  apiClient.delete<ApiResponse<null>>(`/records/${id}`).then((r) => r.data)

export const batchDeleteRecords = (ids: string[]) =>
  apiClient.post<ApiResponse<{ deleted: number }>>('/records/batch-delete', { ids }).then((r) => r.data)

export const clearAllRecords = (source_id?: string) =>
  apiClient.delete<ApiResponse<{ deleted: number }>>('/records', { params: source_id ? { source_id } : {} }).then((r) => r.data)

// ── Schedules ──────────────────────────────────────────────────────────────────
export const listSchedules = (params?: { source_id?: string; enabled?: boolean }) =>
  apiClient.get<ApiResponse<CronSchedule[]>>('/schedules', { params }).then((r) => r.data)

export const createSchedule = (data: Partial<CronSchedule>) =>
  apiClient.post<ApiResponse<CronSchedule>>('/schedules', data).then((r) => r.data.data)

export const updateSchedule = (id: string, data: Partial<CronSchedule>) =>
  apiClient.patch<ApiResponse<CronSchedule>>(`/schedules/${id}`, data).then((r) => r.data.data)

export const deleteSchedule = (id: string) =>
  apiClient.delete<ApiResponse<null>>(`/schedules/${id}`).then((r) => r.data)

// ── Notifications ──────────────────────────────────────────────────────────────
export const listNotificationRules = () =>
  apiClient.get<ApiResponse<NotificationRule[]>>('/notifications/rules').then((r) => r.data)

export const createNotificationRule = (data: Partial<NotificationRule>) =>
  apiClient
    .post<ApiResponse<NotificationRule>>('/notifications/rules', data)
    .then((r) => r.data.data)

export const updateNotificationRule = (id: string, data: Partial<NotificationRule>) =>
  apiClient
    .patch<ApiResponse<NotificationRule>>(`/notifications/rules/${id}`, data)
    .then((r) => r.data.data)

export const deleteNotificationRule = (id: string) =>
  apiClient.delete<ApiResponse<null>>(`/notifications/rules/${id}`).then((r) => r.data)

export const listNotificationLogs = (params?: { rule_id?: string }) =>
  apiClient
    .get<ApiResponse<NotificationLog[]>>('/notifications/logs', { params })
    .then((r) => r.data)

// ── Model Providers ────────────────────────────────────────────────────────────
export const listProviders = () =>
  apiClient.get<ApiResponse<ModelProvider[]>>('/providers').then((r) => r.data)

export const createProvider = (data: Partial<ModelProvider>) =>
  apiClient.post<ApiResponse<ModelProvider>>('/providers', data).then((r) => r.data.data)

export const updateProvider = (id: string, data: Partial<ModelProvider>) =>
  apiClient.patch<ApiResponse<ModelProvider>>(`/providers/${id}`, data).then((r) => r.data.data)

export const deleteProvider = (id: string) =>
  apiClient.delete<ApiResponse<null>>(`/providers/${id}`).then((r) => r.data)

// ── Agents ─────────────────────────────────────────────────────────────────────
export const listAgents = (params?: { enabled?: boolean }) =>
  apiClient.get<ApiResponse<AIAgent[]>>('/agents', { params }).then((r) => r.data)

export const createAgent = (data: Partial<AIAgent>) =>
  apiClient.post<ApiResponse<AIAgent>>('/agents', data).then((r) => r.data.data)

export const updateAgent = (id: string, data: Partial<AIAgent>) =>
  apiClient.patch<ApiResponse<AIAgent>>(`/agents/${id}`, data).then((r) => r.data.data)

export const deleteAgent = (id: string) =>
  apiClient.delete<ApiResponse<null>>(`/agents/${id}`).then((r) => r.data)

// ── Browser bindings ───────────────────────────────────────────────────────────
export const listBrowserBindings = () =>
  apiClient.get<ApiResponse<BrowserBinding[]>>('/browsers/bindings').then((r) => r.data)

export const createBrowserBinding = (data: { browser_endpoint: string; site: string; notes?: string }) =>
  apiClient.post<ApiResponse<BrowserBinding>>('/browsers/bindings', data).then((r) => r.data.data)

export const deleteBrowserBinding = (id: string) =>
  apiClient.delete<ApiResponse<null>>(`/browsers/bindings/${id}`).then((r) => r.data)

export const addChromeInstance = (count = 1, mode: 'bridge' | 'cdp' = 'bridge', node_type: 'local' | 'agent' = 'local') =>
  apiClient.post<ApiResponse<{ created: { endpoint: string; novnc_port: number }[]; total: number }>>(`/browsers/chrome-instances?count=${count}&mode=${mode}&node_type=${node_type}`).then((r) => r.data.data)

export const removeChromeInstance = (n: number) =>
  apiClient.delete<ApiResponse<{ removed: string; total: number }>>(`/browsers/chrome-instances/${n}`).then((r) => r.data)

export const restartApi = () =>
  apiClient.post<ApiResponse<{ restarting: boolean }>>('/browsers/restart-api').then((r) => r.data)

// ── System ─────────────────────────────────────────────────────────────────────
export const getHealth = () =>
  apiClient.get<{ status: string; version: string; task_executor: string }>('/health').then((r) => r.data)

// ── Workers ────────────────────────────────────────────────────────────────────
export const listWorkers = () =>
  apiClient.get<ApiResponse<WorkerNode[]>>('/workers').then((r) => r.data)

export const getCeleryStats = () =>
  apiClient.get<ApiResponse<Record<string, unknown>>>('/workers/celery-stats').then((r) => r.data.data)

export const getChromePool = () =>
  apiClient
    .get<ApiResponse<{ endpoints: ChromeEndpoint[]; total: number; available: number }>>('/workers/chrome-pool')
    .then((r) => r.data.data)

export const updateChromeEndpointMode = (endpoint: string, mode: 'bridge' | 'cdp') => {
  const b64 = btoa(endpoint).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
  return apiClient
    .patch<ApiResponse<{ endpoint: string; mode: string }>>(`/workers/chrome-pool/${b64}/mode`, { mode })
    .then((r) => r.data.data)
}
