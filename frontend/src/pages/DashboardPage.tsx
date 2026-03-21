import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getDashboardStats } from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import { formatInTimeZone } from 'date-fns-tz'
import { Database, Activity, FileText, Zap, CheckCircle, XCircle } from 'lucide-react'

// ── Time range ────────────────────────────────────────────────────────────────

type RangeKey = 'all' | 'today' | 'yesterday' | '7d' | '30d' | 'custom'

const RANGE_LABELS: Record<RangeKey, string> = {
  all: '全部',
  today: '今天',
  yesterday: '昨天',
  '7d': '7 天内',
  '30d': '30 天内',
  custom: '自定义',
}

function TimeRangeBar({
  range,
  customStart,
  customEnd,
  onChange,
  onCustomChange,
}: {
  range: RangeKey
  customStart: string
  customEnd: string
  onChange: (r: RangeKey) => void
  onCustomChange: (start: string, end: string) => void
}) {
  const keys: RangeKey[] = ['all', 'today', 'yesterday', '7d', '30d', 'custom']
  return (
    <div className="flex flex-wrap items-center gap-2 mb-5">
      {keys.map((k) => (
        <button
          key={k}
          onClick={() => onChange(k)}
          className={[
            'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
            range === k
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600',
          ].join(' ')}
        >
          {RANGE_LABELS[k]}
        </button>
      ))}
      {range === 'custom' && (
        <div className="flex items-center gap-2">
          <input
            type="datetime-local"
            value={customStart}
            onChange={(e) => onCustomChange(e.target.value, customEnd)}
            className="text-xs border border-gray-300 dark:border-gray-600 rounded px-2 py-1 dark:bg-gray-700 dark:text-white"
          />
          <span className="text-xs text-gray-400">—</span>
          <input
            type="datetime-local"
            value={customEnd}
            onChange={(e) => onCustomChange(customStart, e.target.value)}
            className="text-xs border border-gray-300 dark:border-gray-600 rounded px-2 py-1 dark:bg-gray-700 dark:text-white"
          />
        </div>
      )}
    </div>
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  color,
}: {
  label: string
  value: number | string
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

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { t } = useTranslation()
  const [range, setRange] = useState<RangeKey>('all')
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')

  const queryParams = (() => {
    if (range === 'custom') {
      return {
        range,
        start: customStart ? new Date(customStart).toISOString() : undefined,
        end: customEnd ? new Date(customEnd).toISOString() : undefined,
      }
    }
    return { range }
  })()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard-stats', range, customStart, customEnd],
    queryFn: () => getDashboardStats(queryParams),
    refetchInterval: 15_000,
  })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorAlert error={error as Error} onRetry={refetch} />
  if (!data) return null

  const runs = data.runs ?? { total: 0, success: 0, failed: 0, success_rate: 0 }

  return (
    <div>
      <PageHeader title={t('dashboard.title')} description={t('dashboard.description')} />

      <TimeRangeBar
        range={range}
        customStart={customStart}
        customEnd={customEnd}
        onChange={setRange}
        onCustomChange={(s, e) => { setCustomStart(s); setCustomEnd(e) }}
      />

      {/* Row 1: Sources + Tasks (global config, not time-filtered) */}
      <div className="grid grid-cols-2 gap-4 mb-4 lg:grid-cols-4">
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

      {/* Row 2: Run stats (time-filtered) */}
      <div className="grid grid-cols-2 gap-4 mb-6 lg:grid-cols-3">
        <StatCard
          label="成功执行次数"
          value={runs.success}
          sub={`共 ${runs.total} 次执行`}
          icon={CheckCircle}
          color="bg-emerald-500"
        />
        <StatCard
          label="失败执行次数"
          value={runs.failed}
          sub={`共 ${runs.total} 次执行`}
          icon={XCircle}
          color="bg-orange-500"
        />
        <StatCard
          label="成功率"
          value={`${runs.success_rate}%`}
          sub={runs.total > 0 ? `${runs.success} / ${runs.total}` : '暂无数据'}
          icon={Activity}
          color="bg-sky-500"
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
