import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listRecords, batchDeleteRecords, clearAllRecords } from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
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
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [confirmClear, setConfirmClear] = useState(false)

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

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['records'] })
    setSelected(new Set())
  }

  const batchDelete = useMutation({
    mutationFn: (ids: string[]) => batchDeleteRecords(ids),
    onSuccess: invalidate,
  })

  const clearAll = useMutation({
    mutationFn: () => clearAllRecords(),
    onSuccess: () => { invalidate(); setConfirmClear(false) },
  })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorAlert error={error as Error} onRetry={refetch} />

  const records: CollectedRecord[] = data?.data ?? []
  const meta = data?.meta
  const allIds = records.map((r) => r.id)
  const allSelected = allIds.length > 0 && allIds.every((id) => selected.has(id))
  const someSelected = selected.size > 0

  const toggleAll = () => {
    if (allSelected) {
      setSelected((prev) => {
        const next = new Set(prev)
        allIds.forEach((id) => next.delete(id))
        return next
      })
    } else {
      setSelected((prev) => new Set([...prev, ...allIds]))
    }
  }

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div>
      <PageHeader title={t('records.title')} description={t('records.description')} />

      {/* Filters + actions bar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {STATUS_FILTERS.map(({ value, label }) => (
          <button
            key={value || 'all'}
            onClick={() => { setStatusFilter(value); setPage(1); setSelected(new Set()) }}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              statusFilter === value
                ? 'bg-blue-600 text-white'
                : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 hover:bg-gray-50'
            }`}
          >
            {label}
          </button>
        ))}

        <div className="ml-auto flex items-center gap-2">
          {someSelected && (
            <button
              onClick={() => batchDelete.mutate([...selected])}
              disabled={batchDelete.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 disabled:opacity-50"
            >
              {batchDelete.isPending ? '删除中…' : `删除已选 (${selected.size})`}
            </button>
          )}
          {!confirmClear ? (
            <button
              onClick={() => setConfirmClear(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 hover:bg-red-50 hover:text-red-600 hover:border-red-200"
            >
              一键清空
            </button>
          ) : (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-red-600">确认清空全部？</span>
              <button
                onClick={() => clearAll.mutate()}
                disabled={clearAll.isPending}
                className="px-2 py-1 rounded text-xs font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {clearAll.isPending ? '清空中…' : '确认'}
              </button>
              <button
                onClick={() => setConfirmClear(false)}
                className="px-2 py-1 rounded text-xs font-medium border border-gray-200 hover:bg-gray-50"
              >
                取消
              </button>
            </div>
          )}
        </div>
      </div>

      <Card padding={false}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <th className="w-10 px-3 py-3">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={(el) => { if (el) el.indeterminate = !allSelected && someSelected }}
                  onChange={toggleAll}
                  className="rounded"
                />
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 text-xs w-20">{t('common.id')}</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 text-xs">{t('records.titleCol')}</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 text-xs w-24">{t('common.status')}</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 text-xs w-40">{t('records.aiEnrichment')}</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 text-xs w-32">{t('records.collectedAt')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50 dark:divide-gray-700/50">
            {records.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-sm text-gray-400">
                  {t('records.noRecords')}
                </td>
              </tr>
            ) : records.map((r) => (
              <tr
                key={r.id}
                className={`transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/30 ${
                  selected.has(r.id) ? 'bg-blue-50 dark:bg-blue-900/10' : ''
                }`}
              >
                <td className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={selected.has(r.id)}
                    onChange={() => toggleOne(r.id)}
                    className="rounded"
                  />
                </td>
                <td className="px-3 py-2.5">
                  <span className="font-mono text-xs text-gray-400">{r.id.slice(0, 8)}</span>
                </td>
                <td className="px-3 py-2.5">
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
                    {Object.entries(r.normalized_data)
                      .filter(([k]) => k.startsWith('extra_'))
                      .length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(r.normalized_data)
                          .filter(([k]) => k.startsWith('extra_'))
                          .map(([k, v]) => (
                            <span
                              key={k}
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                            >
                              <span className="text-gray-400">{k.slice(6)}</span>
                              <span>{String(v)}</span>
                            </span>
                          ))}
                      </div>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge status={r.status} />
                </td>
                <td className="px-3 py-2.5">
                  {r.ai_enrichment
                    ? <JsonViewer data={r.ai_enrichment} />
                    : <span className="text-xs text-gray-400">—</span>}
                </td>
                <td className="px-3 py-2.5">
                  <span className="text-xs text-gray-500">
                    {formatInTimeZone(new Date(r.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {meta && (meta.pages > 1 || meta.total > 0) && (
          <div className="px-5 py-3 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between text-sm">
            <span className="text-gray-500">{t('records.totalRecords', { count: meta.total })}</span>
            {meta.pages > 1 && (
              <div className="flex gap-2">
                <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
                  className="px-3 py-1 border rounded disabled:opacity-50">{t('common.prev')}</button>
                <span className="px-3 py-1">{t('common.pageOf', { page, pages: meta.pages })}</span>
                <button disabled={page >= meta.pages} onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1 border rounded disabled:opacity-50">{t('common.next')}</button>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
