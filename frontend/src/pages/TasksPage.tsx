import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listTasks } from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import { formatInTimeZone } from 'date-fns-tz'

export default function TasksPage() {
  const { t } = useTranslation()
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)

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
        <DataTable
          data={tasks}
          keyFn={(t) => t.id}
          emptyMessage={t('tasks.noTasks')}
          columns={[
            {
              key: 'id',
              header: t('tasks.taskId'),
              render: (row) => (
                <span className="font-mono text-xs text-gray-500">{row.id.slice(0, 12)}…</span>
              ),
              width: '150px',
            },
            {
              key: 'source',
              header: t('tasks.source'),
              render: (row) => (
                <span className="font-mono text-xs">{row.source_id.slice(0, 12)}…</span>
              ),
            },
            {
              key: 'trigger',
              header: t('tasks.trigger'),
              render: (row) => (
                <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs">
                  {row.trigger_type}
                </span>
              ),
              width: '110px',
            },
            {
              key: 'priority',
              header: t('tasks.priority'),
              render: (row) => <span className="text-xs">{row.priority}</span>,
              width: '80px',
            },
            {
              key: 'status',
              header: t('common.status'),
              width: '200px',
              render: (row) => (
                <div className="space-y-1">
                  <StatusBadge status={row.status} />
                  {row.status === 'failed' && row.error_message && (
                    <p className="text-xs text-red-500 break-all leading-relaxed">
                      {row.error_message}
                    </p>
                  )}
                </div>
              ),
            },
            {
              key: 'created',
              header: t('tasks.created'),
              render: (row) => (
                <span className="text-xs text-gray-500">
                  {formatInTimeZone(new Date(row.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                </span>
              ),
              width: '140px',
            },
            {
              key: 'updated_at',
              header: t('common.updatedAt'),
              render: (row) => (
                <span className="text-xs text-gray-500">
                  {formatInTimeZone(new Date(row.updated_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                </span>
              ),
              width: '130px',
            },
          ]}
        />

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
