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
        <table className="w-full text-sm" style={{ tableLayout: 'fixed' }}>
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <th className="px-5 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400" style={{ width: '90px' }}>{t('common.status')}</th>
              <th className="px-5 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400" style={{ width: '200px' }}>{t('sources.title')}</th>
              <th className="px-5 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400" style={{ width: '70px' }}>触发方式</th>
              <th className="px-5 py-2.5 text-right text-xs font-medium text-gray-500 dark:text-gray-400" style={{ width: '70px' }}>{t('dashboard.records')}</th>
              <th className="px-5 py-2.5 text-right text-xs font-medium text-gray-500 dark:text-gray-400" style={{ width: '60px' }}>耗时</th>
              <th className="px-5 py-2.5 text-right text-xs font-medium text-gray-500 dark:text-gray-400" style={{ width: '130px' }}>{t('common.createdAt')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {data.recent_runs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-gray-400">{t('dashboard.noRuns')}</td>
              </tr>
            ) : (
              data.recent_runs.map((run) => (
                <tr key={run.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/30">
                  <td className="px-5 py-3 overflow-hidden"><StatusBadge status={run.status} /></td>
                  <td className="px-5 py-3 overflow-hidden">
                    <p className="font-medium text-gray-800 dark:text-gray-200 truncate">{run.source_name}</p>
                    <p className="font-mono text-xs text-gray-400 truncate">{run.task_id.slice(0, 8)}…</p>
                  </td>
                  <td className="px-5 py-3 overflow-hidden">
                    <span className="text-xs text-gray-500">{run.task_trigger_type}</span>
                  </td>
                  <td className="px-5 py-3 text-right text-gray-500 overflow-hidden">{run.records_collected}</td>
                  <td className="px-5 py-3 text-right text-gray-500 overflow-hidden">
                    {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '—'}
                  </td>
                  <td className="px-5 py-3 text-right text-gray-500 overflow-hidden">
                    {formatInTimeZone(new Date(run.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
