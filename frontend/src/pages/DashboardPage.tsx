import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { getDashboardStats, getDashboardActivity } from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import { formatInTimeZone } from 'date-fns-tz'
import {
  Database, Activity, FileText, Zap,
  CheckCircle, XCircle, TrendingUp, TrendingDown, Minus,
} from 'lucide-react'

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

const TRIGGER_LABELS: Record<string, string> = {
  manual: '手动',
  scheduled: '定时',
  webhook: 'Webhook',
}

function TimeRangeBar({
  range, customStart, customEnd, onChange, onCustomChange,
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

// ── Trend badge ───────────────────────────────────────────────────────────────

function TrendBadge({ current, previous }: { current: number; previous: number }) {
  if (previous === 0 && current === 0) return null
  const diff = current - previous
  const pct = previous > 0 ? Math.round((diff / previous) * 100) : null

  if (diff > 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
        <TrendingUp size={12} />
        {pct !== null ? `+${pct}%` : `+${diff}`}
      </span>
    )
  }
  if (diff < 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-red-500 dark:text-red-400">
        <TrendingDown size={12} />
        {pct !== null ? `${pct}%` : `${diff}`}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-xs font-medium text-gray-400">
      <Minus size={12} />
      持平
    </span>
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label, value, sub, icon: Icon, color, trend,
}: {
  label: string
  value: number | string
  sub?: string
  icon: React.ElementType
  color: string
  trend?: { current: number; previous: number }
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
          <p className="mt-1 text-3xl font-bold text-gray-900 dark:text-white">{value}</p>
          <div className="mt-1 flex items-center gap-2">
            {sub && <p className="text-xs text-gray-400">{sub}</p>}
            {trend && <TrendBadge current={trend.current} previous={trend.previous} />}
          </div>
        </div>
        <span className={`p-2 rounded-lg ${color} flex-shrink-0 ml-3`}>
          <Icon size={20} className="text-white" />
        </span>
      </div>
    </Card>
  )
}

// ── Chart tooltip ─────────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: {
  active?: boolean
  payload?: { name: string; value: number; color: string }[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-2.5 text-xs shadow-lg">
      <p className="font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {p.value}</p>
      ))}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { t } = useTranslation()
  const [range, setRange] = useState<RangeKey>('all')
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')

  const tzOffset = -new Date().getTimezoneOffset() / 60

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

  const { data: activity } = useQuery({
    queryKey: ['dashboard-activity', tzOffset],
    queryFn: () => getDashboardActivity({ days: 7, tz_offset: tzOffset }),
    refetchInterval: 60_000,
  })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorAlert error={error as Error} onRetry={refetch} />
  if (!data) return null

  const runs = data.runs ?? { total: 0, success: 0, failed: 0, success_rate: 0 }
  const daily = activity?.daily ?? []
  const todayData = daily[daily.length - 1]
  const yesterdayData = daily[daily.length - 2]
  const chartData = daily.map((d) => ({ ...d, label: d.date.slice(5).replace('-', '/') }))

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

      {/* Stat cards — row 1 */}
      <div className="grid grid-cols-2 gap-4 mb-4 lg:grid-cols-4">
        <StatCard
          label={t('dashboard.totalSources')}
          value={data.sources.total}
          sub={t('dashboard.enabledSources', { count: data.sources.enabled })}
          icon={Database}
          color="bg-blue-500"
        />
        <StatCard
          label={t('dashboard.recordsCollected')}
          value={data.records.total}
          sub={t('dashboard.aiProcessed', { count: data.records.ai_processed })}
          icon={FileText}
          color="bg-purple-500"
          trend={todayData && yesterdayData
            ? { current: todayData.new_records, previous: yesterdayData.new_records }
            : undefined}
        />
        <StatCard
          label="今日执行"
          value={todayData?.total_runs ?? 0}
          sub={`成功 ${todayData?.success_runs ?? 0} · 失败 ${todayData?.failed_runs ?? 0}`}
          icon={Activity}
          color="bg-green-500"
          trend={todayData && yesterdayData
            ? { current: todayData.total_runs, previous: yesterdayData.total_runs }
            : undefined}
        />
        <StatCard
          label={t('dashboard.failedTasks')}
          value={data.tasks.failed}
          sub={t('dashboard.needsAttention')}
          icon={Zap}
          color="bg-red-500"
        />
      </div>

      {/* Stat cards — row 2: run stats */}
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

      {/* Charts */}
      {daily.length > 0 && (
        <div className="grid grid-cols-1 gap-4 mb-6 lg:grid-cols-2">
          <Card>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">7 天任务执行趋势</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="total_runs" name="总执行" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="success_runs" name="成功" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="failed_runs" name="失败" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">7 天新增采集量</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="new_records" name="新增记录" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      )}

      {/* Recent runs */}
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
                    <span className="text-xs text-gray-500">
                      {TRIGGER_LABELS[run.task_trigger_type] ?? run.task_trigger_type}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right text-gray-500 overflow-hidden">{run.records_collected}</td>
                  <td className="px-5 py-3 text-right text-gray-500 overflow-hidden">
                    {run.duration_ms != null ? `${(run.duration_ms / 1000).toFixed(1)}s` : '—'}
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
