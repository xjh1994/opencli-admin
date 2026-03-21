import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { listTasks, listTaskRuns, listRunEvents } from '../api/endpoints'
import type { CollectionTask, TaskRun, TaskRunEvent } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import { formatInTimeZone } from 'date-fns-tz'
import TruncatedText from '../components/TruncatedText'

// ── Step label map ─────────────────────────────────────────────────────────────

const STEP_LABELS: Record<string, string> = {
  trigger: '触发',
  collect: '采集',
  normalize: '归一化',
  store: '入库',
  ai_process: 'AI 处理',
  notify: '通知',
  complete: '完成',
  failed: '失败',
}

// ── RunEventTimeline ───────────────────────────────────────────────────────────

function levelDot(level: TaskRunEvent['level']): string {
  switch (level) {
    case 'error':   return 'bg-red-500'
    case 'warning': return 'bg-yellow-400'
    default:        return 'bg-blue-500'
  }
}

function formatTime(isoStr: string): string {
  try {
    return formatInTimeZone(new Date(isoStr), 'Asia/Shanghai', 'HH:mm:ss')
  } catch {
    return isoStr
  }
}

function formatElapsed(ms?: number): string {
  if (ms == null) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function RunEventTimeline({ taskId, runId }: { taskId: string; runId: string }) {
  const { data: evts, isLoading } = useQuery({
    queryKey: ['runEvents', taskId, runId],
    queryFn: () => listRunEvents(taskId, runId),
    refetchInterval: 2000,
  })

  if (isLoading) {
    return (
      <div className="px-6 py-3 text-xs text-gray-400 animate-pulse">加载执行跟踪…</div>
    )
  }

  if (!evts || evts.length === 0) {
    return (
      <div className="px-6 py-3 text-xs text-gray-400">暂无执行日志</div>
    )
  }

  return (
    <div className="px-6 py-3 space-y-1.5 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-100 dark:border-gray-700">
      {evts.map((e) => {
        const command = e.detail?.command as string | undefined
        const metadata = e.detail?.metadata as Record<string, unknown> | undefined
        const nodeUrl = (e.detail?.node_url ?? metadata?.node_url) as string | undefined
        const chromeMode = (e.detail?.chrome_mode ?? metadata?.chrome_mode) as string | undefined
        return (
          <div key={e.id} className="flex items-start gap-3 text-xs">
            {/* colored dot + step label */}
            <div className="flex items-center gap-1.5 w-24 shrink-0 pt-0.5">
              <span className={`w-2 h-2 rounded-full shrink-0 ${levelDot(e.level)}`} />
              <span className="text-gray-500 dark:text-gray-400 truncate">
                {STEP_LABELS[e.step] ?? e.step}
              </span>
            </div>
            {/* message + detail */}
            <div className={`flex-1 min-w-0 leading-relaxed ${
              e.level === 'error'   ? 'text-red-600 dark:text-red-400' :
              e.level === 'warning' ? 'text-yellow-600 dark:text-yellow-400' :
              'text-gray-700 dark:text-gray-300'
            }`}>
              <span>{e.message}</span>
              {command && (
                <div className="mt-1 font-mono text-[11px] bg-gray-900 dark:bg-gray-950 text-green-400 rounded px-2 py-1 break-all">
                  $ {command}
                </div>
              )}
              {(nodeUrl || chromeMode) && (
                <div className="mt-0.5 flex items-center gap-2 text-gray-400 dark:text-gray-500">
                  {nodeUrl && <span>节点: {nodeUrl}</span>}
                  {chromeMode && <span>Chrome: {chromeMode}</span>}
                </div>
              )}
            </div>
            {/* timestamp + elapsed */}
            <div className="flex items-center gap-2 shrink-0 text-gray-400 font-mono">
              {e.elapsed_ms != null && (
                <span className="text-gray-400">{formatElapsed(e.elapsed_ms)}</span>
              )}
              <span>{formatTime(e.created_at)}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── TaskRunsPanel ──────────────────────────────────────────────────────────────

function TaskRunsPanel({ task }: { task: CollectionTask }) {
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['taskRuns', task.id],
    queryFn: () => listTaskRuns(task.id),
    refetchInterval: 3000,
  })

  const runs: TaskRun[] = data?.data ?? []

  if (isLoading) {
    return <div className="px-6 py-3 text-xs text-gray-400 animate-pulse">加载执行记录…</div>
  }

  if (runs.length === 0) {
    return <div className="px-6 py-3 text-xs text-gray-400">暂无执行记录</div>
  }

  return (
    <div className="bg-gray-50 dark:bg-gray-800/50 border-t border-gray-100 dark:border-gray-700">
      {runs.map((run) => {
        const isExpanded = expandedRunId === run.id
        return (
          <div key={run.id}>
            {/* Run row */}
            <button
              onClick={() => setExpandedRunId(isExpanded ? null : run.id)}
              className="w-full flex items-center gap-3 px-6 py-2 text-left hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors"
            >
              {isExpanded
                ? <ChevronDown className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                : <ChevronRight className="w-3.5 h-3.5 text-gray-400 shrink-0" />
              }
              <span className={`w-2 h-2 rounded-full shrink-0 ${
                run.status === 'completed' ? 'bg-green-500' :
                run.status === 'failed'    ? 'bg-red-500' :
                'bg-blue-400 animate-pulse'
              }`} />
              <span className="text-xs text-gray-500 font-mono">{run.id.slice(0, 8)}…</span>
              <span className={`text-xs font-medium ${
                run.status === 'completed' ? 'text-green-600 dark:text-green-400' :
                run.status === 'failed'    ? 'text-red-600 dark:text-red-400' :
                'text-blue-600 dark:text-blue-400'
              }`}>
                {run.status}
              </span>
              <span className="text-xs text-gray-400">
                {run.records_collected} 条
              </span>
              {run.duration_ms != null && (
                <span className="text-xs text-gray-400">{formatElapsed(run.duration_ms)}</span>
              )}
              <span className="ml-auto text-xs text-gray-400">
                {formatInTimeZone(new Date(run.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
              </span>
            </button>
            {/* Event timeline */}
            {isExpanded && (
              <RunEventTimeline taskId={task.id} runId={run.id} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── TasksPage ──────────────────────────────────────────────────────────────────

export default function TasksPage() {
  const { t } = useTranslation()
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null)

  const STATUS_FILTERS = [
    { value: 'all',       label: t('tasks.filterAll') },
    { value: 'pending',   label: t('tasks.filterPending') },
    { value: 'running',   label: t('tasks.filterRunning') },
    { value: 'completed', label: t('tasks.filterCompleted') },
    { value: 'failed',    label: t('tasks.filterFailed') },
  ]

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['tasks', status, page],
    queryFn: () => listTasks({ status: status === 'all' ? undefined : status, page, limit: 20 }),
    refetchInterval: 5000,
  })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorAlert error={error as Error} onRetry={refetch} />

  const tasks = data?.data ?? []
  const meta = data?.meta

  return (
    <div>
      <PageHeader title={t('tasks.title')} description={t('tasks.description')} />

      <div className="flex gap-2 mb-4">
        {STATUS_FILTERS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => { setStatus(value); setPage(1) }}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              status === value
                ? 'bg-blue-600 text-white'
                : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <Card padding={false}>
        <div>
          {tasks.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-gray-400">{t('tasks.noTasks')}</div>
          )}
          {tasks.map((task) => {
            const isExpanded = expandedTaskId === task.id
            return (
              <div key={task.id} className="border-b border-gray-100 dark:border-gray-700 last:border-b-0">
                {/* Task row */}
                <div className="flex items-center gap-4 px-5 py-3">
                  {/* Expand toggle */}
                  <button
                    onClick={() => setExpandedTaskId(isExpanded ? null : task.id)}
                    className="p-0.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                    title="查看执行记录"
                  >
                    {isExpanded
                      ? <ChevronDown className="w-4 h-4 text-gray-400" />
                      : <ChevronRight className="w-4 h-4 text-gray-400" />
                    }
                  </button>

                  {/* Source */}
                  <div className="w-48 shrink-0">
                    {task.source_name && (
                      <p className="text-sm font-medium truncate">{task.source_name}</p>
                    )}
                    <p className="font-mono text-xs text-gray-400">{task.source_id.slice(0, 8)}…</p>
                  </div>

                  {/* Status */}
                  <div className="w-36 shrink-0 space-y-1">
                    <StatusBadge status={task.status} />
                    {task.status === 'failed' && task.error_message && (
                      <TruncatedText
                        text={task.error_message}
                        lines={2}
                        className="text-xs text-red-500 leading-relaxed"
                      />
                    )}
                  </div>

                  {/* Trigger */}
                  <div className="w-20 shrink-0">
                    <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs">
                      {task.trigger_type}
                    </span>
                  </div>

                  {/* Created */}
                  <div className="w-28 shrink-0">
                    <span className="text-xs text-gray-500">
                      {formatInTimeZone(new Date(task.created_at), 'Asia/Shanghai', 'MM-dd HH:mm')}
                    </span>
                  </div>

                  {/* Updated */}
                  <div className="w-28 shrink-0">
                    <span className="text-xs text-gray-500">
                      {formatInTimeZone(new Date(task.updated_at), 'Asia/Shanghai', 'MM-dd HH:mm')}
                    </span>
                  </div>

                  {/* Task ID */}
                  <div className="flex-1 text-right">
                    <span className="font-mono text-xs text-gray-400">{task.id.slice(0, 8)}…</span>
                  </div>
                </div>

                {/* Expanded: runs + event timelines */}
                {isExpanded && <TaskRunsPanel task={task} />}
              </div>
            )
          })}
        </div>

        {meta && meta.pages > 1 && (
          <div className="px-5 py-3 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between text-sm">
            <span className="text-gray-500">{t('tasks.totalTasks', { count: meta.total })}</span>
            <div className="flex gap-2">
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1 border rounded disabled:opacity-50">{t('common.prev')}</button>
              <span className="px-3 py-1">{t('common.pageOf', { page, pages: meta.pages })}</span>
              <button disabled={page >= meta.pages} onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 border rounded disabled:opacity-50">{t('common.next')}</button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
