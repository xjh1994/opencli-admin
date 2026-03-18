import { apiClient } from './client'
import type {
  ApiResponse,
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

export const triggerTask = (source_id: string, parameters?: Record<string, unknown>) =>
  apiClient
    .post<ApiResponse<{ task_id: string; celery_task_id: string }>>('/tasks/trigger', {
      source_id,
      parameters: parameters ?? {},
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

// ── System ─────────────────────────────────────────────────────────────────────
export const getHealth = () =>
  apiClient.get<{ status: string; version: string; task_executor: string }>('/health').then((r) => r.data)

// ── Workers ────────────────────────────────────────────────────────────────────
export const listWorkers = () =>
  apiClient.get<ApiResponse<WorkerNode[]>>('/workers').then((r) => r.data)

export const getCeleryStats = () =>
  apiClient.get<ApiResponse<Record<string, unknown>>>('/workers/celery-stats').then((r) => r.data.data)
