import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listWorkers, getCeleryStats, getHealth } from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import { formatInTimeZone } from 'date-fns-tz'
import { Server } from 'lucide-react'

export default function WorkersPage() {
  const { t } = useTranslation()

  const healthQ = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    staleTime: 60_000,
  })

  const isLocalMode = healthQ.data?.task_executor === 'local'

  const workersQ = useQuery({
    queryKey: ['workers'],
    queryFn: listWorkers,
    refetchInterval: 10_000,
    enabled: !isLocalMode,
  })

  const statsQ = useQuery({
    queryKey: ['celery-stats'],
    queryFn: getCeleryStats,
    refetchInterval: 10_000,
    enabled: !isLocalMode,
  })

  const workers = workersQ.data?.data ?? []

  if (healthQ.isLoading) return <PageLoader />

  if (isLocalMode) {
    return (
      <div>
        <PageHeader title={t('workers.title')} description={t('workers.description')} />
        <Card>
          <div className="flex flex-col items-center py-10 text-center gap-4">
            <div className="p-4 bg-gray-100 dark:bg-gray-700 rounded-full">
              <Server size={32} className="text-gray-400" />
            </div>
            <div>
              <p className="text-base font-medium text-gray-700 dark:text-gray-200">单机模式运行中</p>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 max-w-sm">
                当前使用本地 asyncio 执行任务，不支持查看工作节点状态。
                如需分布式部署，请将 <code className="px-1 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs">TASK_EXECUTOR</code> 改为 <code className="px-1 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs">celery</code> 并启动分布式任务服务。
              </p>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div>
      <PageHeader title={t('workers.title')} description={t('workers.description')} />

      <Card className="mb-6">
        <h2 className="font-semibold text-gray-900 dark:text-white mb-3">{t('workers.liveStats')}</h2>
        {statsQ.isLoading ? (
          <p className="text-sm text-gray-400">{t('workers.statsLoading')}</p>
        ) : statsQ.data ? (
          <pre className="text-xs bg-gray-50 dark:bg-gray-900 p-3 rounded-lg overflow-auto max-h-48">
            {JSON.stringify(statsQ.data, null, 2)}
          </pre>
        ) : (
          <p className="text-sm text-gray-400">{t('workers.notReachable')}</p>
        )}
      </Card>

      <Card padding={false}>
        {workersQ.isLoading ? (
          <PageLoader />
        ) : workersQ.error ? (
          <ErrorAlert error={workersQ.error as Error} />
        ) : (
          <DataTable
            data={workers}
            keyFn={(w) => w.id}
            emptyMessage={t('workers.noWorkers')}
            columns={[
              {
                key: 'id', header: t('common.id'), width: '100px',
                render: (w) => <span className="font-mono text-xs text-gray-400">{w.id.slice(0, 8)}</span>,
              },
              { key: 'worker_id', header: t('workers.workerId'), render: (w) => <code className="text-xs">{w.worker_id}</code> },
              { key: 'hostname', header: t('workers.host'), render: (w) => <span className="text-sm">{w.hostname}</span> },
              { key: 'status', header: t('common.status'), render: (w) => <StatusBadge status={w.status} /> },
              { key: 'active', header: t('workers.activeTasks'), render: (w) => <span className="text-sm">{w.active_tasks}</span> },
              {
                key: 'heartbeat',
                header: t('workers.lastHeartbeat'),
                render: (w) => (
                  <span className="text-xs text-gray-500">
                    {w.last_heartbeat
                      ? formatInTimeZone(new Date(w.last_heartbeat), 'Asia/Shanghai', 'MM-dd HH:mm:ss')
                      : '—'}
                  </span>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  )
}
