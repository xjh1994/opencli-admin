import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getDashboardStats } from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import { formatInTimeZone } from 'date-fns-tz'
import { Database, Activity, FileText, Zap } from 'lucide-react'

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  color,
}: {
  label: string
  value: number
  sub?: string
  icon: React.ElementType
  color: string
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
          <p className="mt-1 text-3xl font-bold text-gray-900 dark:text-white">{value}</p>
          {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
        </div>
        <span className={`p-2 rounded-lg ${color}`}>
          <Icon size={20} className="text-white" />
        </span>
      </div>
    </Card>
  )
}

export default function DashboardPage() {
  const { t } = useTranslation()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
    refetchInterval: 15_000,
  })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorAlert error={error as Error} onRetry={refetch} />
  if (!data) return null

  return (
    <div>
      <PageHeader title={t('dashboard.title')} description={t('dashboard.description')} />

      <div className="grid grid-cols-2 gap-4 mb-6 lg:grid-cols-4">
        <StatCard
          label={t('dashboard.totalSources')}
          value={data.sources.total}
          sub={t('dashboard.enabledSources', { count: data.sources.enabled })}
          icon={Database}
          color="bg-blue-500"
        />
        <StatCard
          label={t('dashboard.runningTasks')}
          value={data.tasks.running}
          sub={t('dashboard.totalTasks', { count: data.tasks.total })}
          icon={Activity}
          color="bg-green-500"
        />
        <StatCard
          label={t('dashboard.failedTasks')}
          value={data.tasks.failed}
          sub={t('dashboard.needsAttention')}
          icon={Zap}
          color="bg-red-500"
        />
        <StatCard
          label={t('dashboard.recordsCollected')}
          value={data.records.total}
          sub={t('dashboard.aiProcessed', { count: data.records.ai_processed })}
          icon={FileText}
          color="bg-purple-500"
        />
      </div>

      <Card padding={false}>
        <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="font-semibold text-gray-900 dark:text-white">{t('dashboard.recentRuns')}</h2>
        </div>
        <div className="divide-y divide-gray-100 dark:divide-gray-700">
          {data.recent_runs.length === 0 ? (
            <p className="px-5 py-8 text-center text-gray-400 text-sm">{t('dashboard.noRuns')}</p>
          ) : (
            data.recent_runs.map((run) => (
              <div key={run.id} className="px-5 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <StatusBadge status={run.status} />
                  <span className="text-sm text-gray-600 dark:text-gray-300 font-mono">
                    {run.task_id.slice(0, 8)}…
                  </span>
                </div>
                <div className="flex items-center gap-6 text-sm text-gray-500">
                  <span>{run.records_collected} {t('dashboard.records')}</span>
                  {run.duration_ms && <span>{(run.duration_ms / 1000).toFixed(1)}s</span>}
                  <span>
                    {formatInTimeZone(new Date(run.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  )
}
