import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { listRecords, batchDeleteRecords, clearAllRecords, listSources } from '../api/endpoints'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import { TableSkeleton } from '../components/SkeletonLoader'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import Pagination from '../components/Pagination'
import { Input } from '@/components/ui/input'
import { formatInTimeZone } from 'date-fns-tz'
import { FileText, Search, ChevronDown, ChevronRight } from 'lucide-react'
import type { CollectedRecord } from '../api/types'

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState<T>(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

function JsonBlock({ data }: { data: Record<string, unknown> }) {
  return (
    <pre className="text-xs bg-gray-900 text-gray-100 p-3 rounded overflow-auto max-h-64 font-mono">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

export default function RecordsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [confirmClearOpen, setConfirmClearOpen] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const search = useDebounce(searchInput, 400)

  const STATUS_FILTERS = [
    { value: '',             label: t('records.filterAll') },
    { value: 'raw',          label: t('records.filterRaw') },
    { value: 'normalized',   label: t('records.filterNormalized') },
    { value: 'ai_processed', label: t('records.filterAiProcessed') },
    { value: 'error',        label: t('records.filterError') },
  ]

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['records', page, statusFilter, search],
    queryFn: () =>
      listRecords({
        page,
        limit: 20,
        status: statusFilter || undefined,
        search: search || undefined,
      }),
  })

  const { data: sourcesData } = useQuery({
    queryKey: ['sources', 'all'],
    queryFn: () => listSources({ limit: 200 }),
  })

  const sourceMap: Record<string, string> = {}
  for (const s of sourcesData?.data ?? []) {
    sourceMap[s.id] = s.name
  }

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['records'] })
    setSelected(new Set())
  }

  const batchDelete = useMutation({
    mutationFn: (ids: string[]) => batchDeleteRecords(ids),
    onSuccess: () => { invalidate(); toast.success('已批量删除') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '删除失败'),
  })

  const clearAll = useMutation({
    mutationFn: () => clearAllRecords(),
    onSuccess: () => { invalidate(); setConfirmClearOpen(false); toast.success('已清空') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '操作失败'),
  })

  if (isLoading) return (
    <div>
      <PageHeader title={t('records.title')} description={t('records.description')} />
      <Card padding={false}><TableSkeleton rows={8} /></Card>
    </div>
  )
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

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  return (
    <div>
      <PageHeader title={t('records.title')} description={t('records.description')} />

      {/* Search bar */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
        <Input
          value={searchInput}
          onChange={(e) => {
            setSearchInput(e.target.value)
            setPage(1)
          }}
          placeholder="搜索标题、内容..."
          className="pl-9"
        />
      </div>

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
          <button
            onClick={() => setConfirmClearOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 hover:bg-red-50 hover:text-red-600 hover:border-red-200"
          >
            一键清空
          </button>
        </div>
      </div>

      <Card padding={false}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <th className="w-8 px-2 py-3" />
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
              <th className="px-3 py-3 text-left font-medium text-gray-500 text-xs">来源</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 text-xs w-80 max-w-xs">{t('records.titleCol')}</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 text-xs w-24">{t('common.status')}</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 text-xs w-32">{t('records.collectedAt')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50 dark:divide-gray-700/50">
            {records.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <EmptyState
                    icon={FileText}
                    title="暂无采集记录"
                    description="触发一次采集任务后，数据将在此展示"
                  />
                </td>
              </tr>
            ) : records.map((r) => (
              <>
                <tr
                  key={r.id}
                  onClick={() => toggleExpand(r.id)}
                  className={`cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/30 ${
                    selected.has(r.id) ? 'bg-blue-50 dark:bg-blue-900/10' : ''
                  }`}
                >
                  <td className="px-2 py-2.5 text-gray-400">
                    {expandedId === r.id
                      ? <ChevronDown className="h-4 w-4" />
                      : <ChevronRight className="h-4 w-4" />}
                  </td>
                  <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
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
                    <span className="text-xs text-gray-600 dark:text-gray-300">
                      {sourceMap[r.source_id] ?? r.source_id.slice(0, 8)}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 w-80 max-w-xs">
                    <div className="space-y-1">
                      <p className="font-medium text-sm truncate" title={(r.normalized_data.title as string) || ''}>
                        {(r.normalized_data.title as string) || '—'}
                      </p>
                      {typeof r.normalized_data.url === 'string' && r.normalized_data.url && (
                        <a
                          href={r.normalized_data.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs text-blue-500 hover:underline block truncate"
                        >
                          {r.normalized_data.url.slice(0, 60)}
                        </a>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="text-xs text-gray-500">
                      {formatInTimeZone(new Date(r.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                    </span>
                  </td>
                </tr>
                {expandedId === r.id && (
                  <tr key={`${r.id}-detail`} className="bg-gray-50 dark:bg-gray-800/20">
                    <td colSpan={7} className="px-6 py-4">
                      <div className="space-y-4">
                        <div>
                          <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">标准化数据</p>
                          <JsonBlock data={r.normalized_data} />
                        </div>
                        {r.ai_enrichment && (
                          <div>
                            <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">AI 分析</p>
                            <JsonBlock data={r.ai_enrichment} />
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>

        {meta && (meta.pages > 1 || meta.total > 0) && (
          <Pagination
            page={page}
            pages={meta.pages}
            total={meta.total}
            limit={20}
            onChange={setPage}
          />
        )}
      </Card>

      <ConfirmDialog
        open={confirmClearOpen}
        onOpenChange={setConfirmClearOpen}
        title="确认清空全部记录？"
        description="此操作不可撤销，所有采集记录将被永久删除。"
        confirmLabel={clearAll.isPending ? '清空中…' : '确认清空'}
        variant="destructive"
        onConfirm={() => clearAll.mutate()}
      />
    </div>
  )
}
