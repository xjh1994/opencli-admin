import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listRecords } from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import { formatInTimeZone } from 'date-fns-tz'
import type { CollectedRecord } from '../api/types'

function JsonViewer({ data }: { data: Record<string, unknown> }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const preview = JSON.stringify(data).slice(0, 60)
  return (
    <div>
      <button
        onClick={() => setExpanded((e) => !e)}
        className="text-xs text-blue-500 hover:underline"
      >
        {expanded ? t('common.collapse') : preview + (preview.length >= 60 ? '…' : '')}
      </button>
      {expanded && (
        <pre className="mt-1 text-xs bg-gray-50 dark:bg-gray-900 p-2 rounded max-w-xs overflow-auto max-h-40">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}

export default function RecordsPage() {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')

  const STATUS_FILTERS = [
    { value: '',             label: t('records.filterAll') },
    { value: 'raw',          label: t('records.filterRaw') },
    { value: 'normalized',   label: t('records.filterNormalized') },
    { value: 'ai_processed', label: t('records.filterAiProcessed') },
    { value: 'error',        label: t('records.filterError') },
  ]

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['records', page, statusFilter],
    queryFn: () => listRecords({ page, limit: 20, status: statusFilter || undefined }),
  })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorAlert error={error as Error} onRetry={refetch} />

  const records: CollectedRecord[] = data?.data ?? []
  const meta = data?.meta

  return (
    <div>
      <PageHeader title={t('records.title')} description={t('records.description')} />

      <div className="flex gap-2 mb-4">
        {STATUS_FILTERS.map(({ value, label }) => (
          <button
            key={value || 'all'}
            onClick={() => { setStatusFilter(value); setPage(1) }}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              statusFilter === value
                ? 'bg-blue-600 text-white'
                : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 hover:bg-gray-50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <Card padding={false}>
        <DataTable
          data={records}
          keyFn={(r) => r.id}
          emptyMessage={t('records.noRecords')}
          columns={[
            {
              key: 'id',
              header: t('common.id'),
              width: '100px',
              render: (r) => (
                <span className="font-mono text-xs text-gray-400">{r.id.slice(0, 8)}</span>
              ),
            },
            {
              key: 'title',
              header: t('records.titleCol'),
              render: (r) => {
                const extras = Object.entries(r.normalized_data)
                  .filter(([k]) => k.startsWith('extra_'))
                  .map(([k, v]) => ({ key: k.slice(6), value: String(v) }))
                return (
                  <div className="space-y-1">
                    <p className="font-medium text-sm">
                      {(r.normalized_data.title as string) || '—'}
                    </p>
                    {typeof r.normalized_data.url === 'string' && r.normalized_data.url && (
                      <a
                        href={r.normalized_data.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-500 hover:underline block"
                      >
                        {r.normalized_data.url.slice(0, 60)}
                      </a>
                    )}
                    {extras.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {extras.map(({ key, value }) => (
                          <span
                            key={key}
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                          >
                            <span className="text-gray-400">{key}</span>
                            <span>{value}</span>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )
              },
            },
            {
              key: 'status',
              header: t('common.status'),
              render: (r) => <StatusBadge status={r.status} />,
              width: '120px',
            },
            {
              key: 'ai',
              header: t('records.aiEnrichment'),
              render: (r) =>
                r.ai_enrichment ? (
                  <JsonViewer data={r.ai_enrichment} />
                ) : (
                  <span className="text-xs text-gray-400">—</span>
                ),
            },
            {
              key: 'created',
              header: t('records.collectedAt'),
              render: (r) => (
                <span className="text-xs text-gray-500">
                  {formatInTimeZone(new Date(r.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                </span>
              ),
              width: '140px',
            },
            {
              key: 'updated_at',
              header: t('common.updatedAt'),
              render: (r) => (
                <span className="text-xs text-gray-500">
                  {formatInTimeZone(new Date(r.updated_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                </span>
              ),
              width: '130px',
            },
          ]}
        />

        {meta && meta.pages > 1 && (
          <div className="px-5 py-3 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between text-sm">
            <span className="text-gray-500">{t('records.totalRecords', { count: meta.total })}</span>
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
