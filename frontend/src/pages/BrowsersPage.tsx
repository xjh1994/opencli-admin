import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  getChromePool,
  listBrowserBindings,
  createBrowserBinding,
  deleteBrowserBinding,
  addChromeInstance,
  removeChromeInstance,
  restartApi,
} from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import PageHeader from '../components/PageHeader'
import { SITE_LABELS } from '../components/ChannelConfigForm'
import { Plus, X, ExternalLink, RefreshCw, Trash2 } from 'lucide-react'
import type { BrowserBinding } from '../api/types'

function chromeNovncPort(cdpUrl: string, basePort = 3010): number {
  try {
    const hostname = new URL(cdpUrl).hostname
    const m = hostname.match(/^chrome(?:-(\d+))?$/)
    const n = m ? parseInt(m[1] ?? '1', 10) : 1
    return basePort + (n - 1)
  } catch {
    return basePort
  }
}

function instanceLabel(cdpUrl: string): string {
  return cdpUrl.replace('http://', '').replace(':19222', '')
}

function instanceIndex(cdpUrl: string): number | null {
  try {
    const hostname = new URL(cdpUrl).hostname
    const m = hostname.match(/^chrome(?:-(\d+))?$/)
    if (!m) return null
    return m[1] ? parseInt(m[1], 10) : null  // null = instance 1 (compose-managed)
  } catch {
    return null
  }
}

// ── Site dropdown ─────────────────────────────────────────────────────────────

interface SiteDropdownProps {
  boundSites: Set<string>
  onSelect: (site: string) => void
  isPending: boolean
}

function SiteDropdown({ boundSites, onSelect, isPending }: SiteDropdownProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
        setQuery('')
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const available = Object.entries(SITE_LABELS).filter(
    ([key, label]) =>
      !boundSites.has(key) &&
      (!query || key.includes(query.toLowerCase()) || label.includes(query))
  )

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={isPending}
        className="flex items-center gap-1 px-2 py-1 rounded-full text-xs border border-dashed border-gray-300 dark:border-gray-600 text-gray-500 hover:border-blue-400 hover:text-blue-500 transition-colors disabled:opacity-50"
      >
        <Plus size={11} />
        {t('browsers.addSite')}
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1 z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg w-48 overflow-hidden">
          <div className="p-2 border-b border-gray-100 dark:border-gray-700">
            <input
              autoFocus
              className="w-full px-2 py-1 text-xs rounded border border-gray-200 dark:border-gray-600 bg-transparent dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder={t('browsers.searchSite')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <ul className="max-h-52 overflow-y-auto py-1">
            {available.length === 0 ? (
              <li className="px-3 py-2 text-xs text-gray-400">{t('browsers.noAvailable')}</li>
            ) : available.map(([key, label]) => (
              <li key={key}>
                <button
                  onClick={() => { onSelect(key); setOpen(false); setQuery('') }}
                  className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center justify-between"
                >
                  <span className="font-medium dark:text-white">{label}</span>
                  <span className="text-gray-400 font-mono">{key}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Instance card ─────────────────────────────────────────────────────────────

interface InstanceCardProps {
  url: string
  available: boolean
  novncPort: number
  bindings: BrowserBinding[]
  boundSites: Set<string>
  onBind: (site: string) => void
  onUnbind: (id: string) => void
  onRemove?: () => void
  isBindPending: boolean
  isRemovePending: boolean
}

function InstanceCard({
  url, available, novncPort, bindings, boundSites,
  onBind, onUnbind, onRemove, isBindPending, isRemovePending,
}: InstanceCardProps) {
  const { t } = useTranslation()
  const novncUrl = `http://${window.location.hostname}:${novncPort}`
  const label = instanceLabel(url)
  const idx = instanceIndex(url)
  const canRemove = idx !== null && onRemove  // instance 1 is compose-managed

  return (
    <Card>
      <div className="flex items-center gap-2 mb-4 pb-3 border-b border-gray-100 dark:border-gray-700">
        <span className={`w-2 h-2 rounded-full shrink-0 ${available ? 'bg-green-500' : 'bg-red-400'}`} />
        <span className="font-semibold text-sm dark:text-white">{label}</span>
        <a
          href={novncUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-blue-500 hover:underline font-mono"
        >
          :{novncPort}
          <ExternalLink size={11} />
        </a>
        {canRemove && (
          <button
            onClick={onRemove}
            disabled={isRemovePending}
            title={t('browsers.removeInstance')}
            className="ml-auto text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-2 min-h-[2rem]">
        {bindings.map((b) => (
          <span
            key={b.id}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700"
          >
            {SITE_LABELS[b.site] ?? b.site}
            <button onClick={() => onUnbind(b.id)} className="hover:text-red-500 transition-colors ml-0.5">
              <X size={10} />
            </button>
          </span>
        ))}
        <SiteDropdown boundSites={boundSites} onSelect={onBind} isPending={isBindPending} />
      </div>
    </Card>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function BrowsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [restartMsg, setRestartMsg] = useState<string | null>(null)

  const invalidatePool = () => {
    queryClient.invalidateQueries({ queryKey: ['chrome-pool'] })
    queryClient.invalidateQueries({ queryKey: ['browser-bindings'] })
  }

  const { data: poolData, isLoading: poolLoading, error: poolError, refetch } = useQuery({
    queryKey: ['chrome-pool'],
    queryFn: getChromePool,
    refetchInterval: 10_000,
  })

  const { data: bindingsData, isLoading: bindingsLoading } = useQuery({
    queryKey: ['browser-bindings'],
    queryFn: listBrowserBindings,
  })

  const addMutation = useMutation({
    mutationFn: createBrowserBinding,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['browser-bindings'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteBrowserBinding,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['browser-bindings'] }),
  })

  const addInstanceMutation = useMutation({
    mutationFn: addChromeInstance,
    onSuccess: () => { invalidatePool(); setTimeout(() => invalidatePool(), 3000) },
  })

  const removeInstanceMutation = useMutation({
    mutationFn: removeChromeInstance,
    onSuccess: invalidatePool,
  })

  const restartMutation = useMutation({
    mutationFn: restartApi,
    onSuccess: () => {
      setRestartMsg(t('browsers.restarting'))
      // Poll until API is back
      const poll = setInterval(() => {
        fetch('/api/v1/health').then((r) => {
          if (r.ok) { clearInterval(poll); setRestartMsg(null); invalidatePool() }
        }).catch(() => {})
      }, 2000)
      setTimeout(() => { clearInterval(poll); setRestartMsg(null) }, 30_000)
    },
  })

  if (poolLoading || bindingsLoading) return <PageLoader />
  if (poolError) return <ErrorAlert error={poolError as Error} onRetry={refetch} />

  const endpoints = poolData?.endpoints ?? []
  const bindings = bindingsData?.data ?? []

  const bindingsByEndpoint: Record<string, BrowserBinding[]> = {}
  for (const ep of endpoints) bindingsByEndpoint[ep.url] = []
  for (const b of bindings) {
    if (!bindingsByEndpoint[b.browser_endpoint]) bindingsByEndpoint[b.browser_endpoint] = []
    bindingsByEndpoint[b.browser_endpoint].push(b)
  }

  const boundSites = new Set(bindings.map((b) => b.site))
  const orphaned = bindings.filter((b) => !endpoints.find((e) => e.url === b.browser_endpoint))

  return (
    <div>
      <PageHeader title={t('browsers.title')} description={t('browsers.description')} />

      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-5">
        <button
          onClick={() => addInstanceMutation.mutate()}
          disabled={addInstanceMutation.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <Plus size={15} />
          {addInstanceMutation.isPending ? t('browsers.adding') : t('browsers.addInstance')}
        </button>

        <button
          onClick={() => restartMutation.mutate()}
          disabled={restartMutation.isPending || !!restartMsg}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
        >
          <RefreshCw size={15} className={restartMsg ? 'animate-spin' : ''} />
          {restartMsg ?? t('browsers.restartApi')}
        </button>

        {addInstanceMutation.isError && (
          <span className="text-xs text-red-500">
            {(addInstanceMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? t('common.error')}
          </span>
        )}
      </div>

      {/* Instance cards */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {endpoints.map((ep) => {
          const novncPort = ep.novnc_port ?? chromeNovncPort(ep.url)
          const idx = instanceIndex(ep.url)
          return (
            <InstanceCard
              key={ep.url}
              url={ep.url}
              available={ep.available}
              novncPort={novncPort}
              bindings={bindingsByEndpoint[ep.url] ?? []}
              boundSites={boundSites}
              onBind={(site) => addMutation.mutate({ browser_endpoint: ep.url, site })}
              onUnbind={(id) => deleteMutation.mutate(id)}
              onRemove={idx !== null ? () => removeInstanceMutation.mutate(idx) : undefined}
              isBindPending={addMutation.isPending}
              isRemovePending={removeInstanceMutation.isPending}
            />
          )
        })}

        {endpoints.length === 0 && (
          <div className="col-span-full text-center py-12 text-gray-400 text-sm">
            {t('browsers.noInstances')}
          </div>
        )}
      </div>

      {/* Orphaned bindings */}
      {orphaned.length > 0 && (
        <div className="mt-6">
          <p className="text-xs font-medium text-gray-400 mb-2">{t('browsers.orphaned')}</p>
          <Card>
            <div className="flex flex-wrap gap-2">
              {orphaned.map((b) => (
                <span key={b.id} className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 border border-gray-200 dark:border-gray-600">
                  {SITE_LABELS[b.site] ?? b.site}
                  <span className="font-mono text-gray-400">→ {instanceLabel(b.browser_endpoint)}</span>
                  <button onClick={() => deleteMutation.mutate(b.id)} className="hover:text-red-500 ml-0.5">
                    <X size={10} />
                  </button>
                </span>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
