import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Monitor, ExternalLink } from 'lucide-react'
import { listWorkers, getCeleryStats, getHealth, getChromePool, updateChromeEndpointMode } from '../api/endpoints'
import { ChromeEndpoint } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import { formatInTimeZone } from 'date-fns-tz'

function ModeToggle({ endpoint, onSuccess }: { endpoint: ChromeEndpoint; onSuccess: () => void }) {
  const { t } = useTranslation()
  const [optimisticMode, setOptimisticMode] = useState<'bridge' | 'cdp' | null>(null)
  const mode = optimisticMode ?? endpoint.mode

  const mutation = useMutation({
    mutationFn: (newMode: 'bridge' | 'cdp') => updateChromeEndpointMode(endpoint.url, newMode),
    onMutate: (newMode) => setOptimisticMode(newMode),
    onSuccess: () => { setOptimisticMode(null); onSuccess() },
    onError: () => setOptimisticMode(null),
  })

  return (
    <div className="flex rounded-md overflow-hidden border border-gray-200 dark:border-gray-600 text-xs font-medium">
      {(['bridge', 'cdp'] as const).map((m) => (
        <button
          key={m}
          title={t(`workers.mode${m.charAt(0).toUpperCase() + m.slice(1)}Hint`)}
          disabled={mutation.isPending}
          onClick={() => mode !== m && mutation.mutate(m)}
          className={[
            'px-3 py-1 transition-colors',
            mode === m
              ? m === 'bridge'
                ? 'bg-blue-600 text-white'
                : 'bg-amber-500 text-white'
              : 'bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700',
          ].join(' ')}
        >
          {t(`workers.mode${m.charAt(0).toUpperCase() + m.slice(1)}`)}
        </button>
      ))}
    </div>
  )
}

function ChromePoolSection() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const poolQ = useQuery({
    queryKey: ['chrome-pool'],
    queryFn: getChromePool,
    refetchInterval: 15_000,
  })

  const pool = poolQ.data

  return (
    <Card className="mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Monitor size={16} />
            {t('workers.chromePool')}
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{t('workers.chromePoolDesc')}</p>
        </div>
        {pool && (
          <span className="text-xs text-gray-400">
            {pool.available}/{pool.total} available
          </span>
        )}
      </div>

      {poolQ.isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : poolQ.error ? (
        <ErrorAlert error={poolQ.error as Error} />
      ) : !pool?.endpoints.length ? (
        <p className="text-sm text-gray-400">No Chrome instances in pool.</p>
      ) : (
        <div className="divide-y divide-gray-100 dark:divide-gray-700">
          {pool.endpoints.map((ep) => (
            <div key={ep.url} className="flex items-center justify-between py-3 gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <div className={[
                  'w-2 h-2 rounded-full flex-shrink-0',
                  ep.container_status === 'running' ? 'bg-green-400' : 'bg-gray-300',
                ].join(' ')} />
                <div className="min-w-0">
                  <p className="text-sm font-mono text-gray-700 dark:text-gray-200 truncate">{ep.url}</p>
                  <p className="text-xs text-gray-400">{t('workers.containerStatus')}: {ep.container_status ?? '—'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <a
                  href={`http://${new URL(ep.url).hostname.replace(/^chrome(-\d+)?$/, (_, n) => `localhost`)}:${ep.novnc_port}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-500 hover:text-blue-600 flex items-center gap-1"
                >
                  {t('workers.noVnc')} <ExternalLink size={11} />
                </a>
                <ModeToggle
                  endpoint={ep}
                  onSuccess={() => queryClient.invalidateQueries({ queryKey: ['chrome-pool'] })}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

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

  return (
    <div>
      <PageHeader title={t('workers.title')} description={t('workers.description')} />

      <ChromePoolSection />

      {isLocalMode ? null : (
        <>
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
        </>
      )}
    </div>
  )
}
