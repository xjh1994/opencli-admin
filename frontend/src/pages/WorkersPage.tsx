import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listWorkers, getCeleryStats } from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import { formatInTimeZone } from 'date-fns-tz'

export default function WorkersPage() {
  const { t } = useTranslation()

  const workersQ = useQuery({
    queryKey: ['workers'],
    queryFn: listWorkers,
    refetchInterval: 10_000,
  })

  const statsQ = useQuery({
    queryKey: ['celery-stats'],
    queryFn: getCeleryStats,
    refetchInterval: 10_000,
  })

  const workers = workersQ.data?.data ?? []

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
              {
                key: 'created_at', header: t('common.createdAt'), width: '130px',
                render: (w) => (
                  <span className="text-xs text-gray-500">
                    {formatInTimeZone(new Date(w.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                  </span>
                ),
              },
              {
                key: 'updated_at', header: t('common.updatedAt'), width: '130px',
                render: (w) => (
                  <span className="text-xs text-gray-500">
                    {formatInTimeZone(new Date(w.updated_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
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
