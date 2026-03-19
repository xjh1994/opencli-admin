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
  updateChromeEndpointMode,
} from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import PageHeader from '../components/PageHeader'
import { SITE_LABELS } from '../components/ChannelConfigForm'
import { Plus, X, ExternalLink, RefreshCw, Trash2, Minus } from 'lucide-react'
import type { BrowserBinding, ChromeEndpoint } from '../api/types'

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
    return m[1] ? parseInt(m[1], 10) : null
  } catch {
    return null
  }
}

// ── Container status badge ────────────────────────────────────────────────────

interface StatusBadgeProps {
  containerStatus?: string
  available: boolean
  isStarting?: boolean
}

function StatusBadge({ containerStatus, available, isStarting }: StatusBadgeProps) {
  const { t } = useTranslation()

  if (isStarting) {
    return (
      <span className="inline-flex items-center gap-1 text-xs">
        <span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse shrink-0" />
        <span className="text-orange-600 dark:text-orange-400">{t('browsers.statusStarting')}</span>
      </span>
    )
  }

  if (containerStatus === 'running') {
    if (available) {
      return (
        <span className="inline-flex items-center gap-1 text-xs">
          <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
          <span className="text-green-600 dark:text-green-400">{t('browsers.statusIdle')}</span>
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 text-xs">
        <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
        <span className="text-amber-600 dark:text-amber-400">{t('browsers.statusBusy')}</span>
      </span>
    )
  }

  if (containerStatus === 'created' || containerStatus === 'restarting') {
    return (
      <span className="inline-flex items-center gap-1 text-xs">
        <span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse shrink-0" />
        <span className="text-orange-600 dark:text-orange-400">{t('browsers.statusStarting')}</span>
      </span>
    )
  }

  if (containerStatus === 'exited' || containerStatus === 'dead') {
    return (
      <span className="inline-flex items-center gap-1 text-xs">
        <span className="w-2 h-2 rounded-full bg-gray-400 shrink-0" />
        <span className="text-gray-500 dark:text-gray-400">{t('browsers.statusOffline')}</span>
      </span>
    )
  }

  // unknown / undefined — pending restart
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse shrink-0" />
      <span className="text-yellow-600 dark:text-yellow-400">{t('browsers.statusPending')}</span>
    </span>
  )
}

// ── Add Instances Modal ───────────────────────────────────────────────────────

interface AddInstanceModalProps {
  currentCount: number
  onConfirm: (count: number, withRestart: boolean) => void
  onClose: () => void
  isPending: boolean
}

function AddInstanceModal({ currentCount, onConfirm, onClose, isPending }: AddInstanceModalProps) {
  const { t } = useTranslation()
  const [count, setCount] = useState(1)

  const preview = Array.from({ length: count }, (_, i) => {
    const N = currentCount + 1 + i
    return `chrome-${N}`
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-80 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-sm font-semibold dark:text-white mb-4">{t('browsers.addInstanceTitle')}</h3>

        {/* Count picker */}
        <div className="flex items-center gap-3 mb-4">
          <span className="text-xs text-gray-500 dark:text-gray-400 flex-1">{t('browsers.instanceCount')}</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCount((c) => Math.max(1, c - 1))}
              disabled={count <= 1}
              className="w-7 h-7 flex items-center justify-center rounded-full border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:border-blue-400"
            >
              <Minus size={12} />
            </button>
            <span className="w-6 text-center text-sm font-medium dark:text-white">{count}</span>
            <button
              onClick={() => setCount((c) => Math.min(10, c + 1))}
              disabled={count >= 10}
              className="w-7 h-7 flex items-center justify-center rounded-full border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:border-blue-400"
            >
              <Plus size={12} />
            </button>
          </div>
        </div>

        {/* Preview */}
        <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg px-3 py-2 mb-5">
          <p className="text-xs text-gray-400 mb-1.5">{t('browsers.instancePreview')}</p>
          <div className="flex flex-wrap gap-1.5">
            {preview.map((name) => (
              <span key={name} className="px-2 py-0.5 text-xs rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-mono">
                {name}
              </span>
            ))}
          </div>
        </div>

        {/* Actions — two confirm buttons */}
        <div className="flex flex-col gap-2">
          <button
            onClick={() => onConfirm(count, true)}
            disabled={isPending}
            className="w-full px-3 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            {isPending ? t('browsers.adding') : t('browsers.createAndRestart')}
          </button>
          <button
            onClick={() => onConfirm(count, false)}
            disabled={isPending}
            className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
          >
            {t('browsers.createLaterRestart')}
          </button>
          <button
            onClick={onClose}
            disabled={isPending}
            className="w-full px-3 py-1.5 text-xs text-gray-400 hover:text-gray-600 disabled:opacity-50"
          >
            {t('common.cancel')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Remove Instance Modal ─────────────────────────────────────────────────────

interface RemoveInstanceModalProps {
  name: string
  onConfirm: (withRestart: boolean) => void
  onClose: () => void
  isPending: boolean
}

function RemoveInstanceModal({ name, onConfirm, onClose, isPending }: RemoveInstanceModalProps) {
  const { t } = useTranslation()
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-80 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-sm font-semibold dark:text-white mb-2">{t('browsers.removeInstance')}</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-5">
          {t('browsers.confirmRemove', { name })}
        </p>
        <div className="flex flex-col gap-2">
          <button
            onClick={() => onConfirm(true)}
            disabled={isPending}
            className="w-full px-3 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 font-medium"
          >
            {isPending ? t('common.loading') : t('browsers.removeAndRestart')}
          </button>
          <button
            onClick={() => onConfirm(false)}
            disabled={isPending}
            className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
          >
            {t('browsers.removeLaterRestart')}
          </button>
          <button
            onClick={onClose}
            disabled={isPending}
            className="w-full px-3 py-1.5 text-xs text-gray-400 hover:text-gray-600 disabled:opacity-50"
          >
            {t('common.cancel')}
          </button>
        </div>
      </div>
    </div>
  )
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
            'px-2.5 py-1 transition-colors',
            mode === m
              ? m === 'bridge'
                ? 'bg-blue-600 text-white'
                : 'bg-amber-500 text-white'
              : 'bg-white dark:bg-gray-800 text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700',
          ].join(' ')}
        >
          {t(`workers.mode${m.charAt(0).toUpperCase() + m.slice(1)}`)}
        </button>
      ))}
    </div>
  )
}

interface InstanceCardProps {
  endpoint: ChromeEndpoint
  isStarting?: boolean
  bindings: BrowserBinding[]
  boundSites: Set<string>
  onBind: (site: string) => void
  onUnbind: (id: string) => void
  onRemove?: () => void
  isBindPending: boolean
  isRemovePending: boolean
  onModeChanged: () => void
}

function InstanceCard({
  endpoint, isStarting, bindings, boundSites,
  onBind, onUnbind, onRemove, isBindPending, isRemovePending, onModeChanged,
}: InstanceCardProps) {
  const { t } = useTranslation()
  const { url, available, container_status: containerStatus, novnc_port: novncPort } = endpoint
  const novncUrl = `http://${window.location.hostname}:${novncPort}`
  const label = instanceLabel(url)
  const idx = instanceIndex(url)
  const canRemove = idx !== null && idx > 1 && onRemove

  return (
    <Card>
      <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-100 dark:border-gray-700">
        <StatusBadge containerStatus={containerStatus} available={available} isStarting={isStarting} />
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
        <div className="ml-auto flex items-center gap-2">
          <ModeToggle endpoint={endpoint} onSuccess={onModeChanged} />
          {canRemove && (
            <button
              onClick={onRemove}
              disabled={isRemovePending}
              title={t('browsers.removeInstance')}
              className="text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
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
  const [showAddModal, setShowAddModal] = useState(false)
  const [startingEndpoints, setStartingEndpoints] = useState<Set<string>>(new Set())
  const [removingIdx, setRemovingIdx] = useState<number | null>(null)

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
    mutationFn: ({ count }: { count: number; withRestart: boolean }) => addChromeInstance(count),
    onSuccess: (result, { withRestart }) => {
      setShowAddModal(false)
      invalidatePool()
      if (withRestart) {
        restartMutation.mutate()
      } else {
        const newUrls = new Set(result.created.map((c) => c.endpoint))
        setStartingEndpoints((prev) => new Set([...prev, ...newUrls]))
        // After 30s clear the "启动中" hint and refresh
        setTimeout(() => {
          setStartingEndpoints((prev) => {
            const next = new Set(prev)
            newUrls.forEach((url) => next.delete(url))
            return next
          })
          invalidatePool()
        }, 30_000)
      }
    },
  })

  const removeInstanceMutation = useMutation({
    mutationFn: ({ idx }: { idx: number; withRestart: boolean }) => removeChromeInstance(idx),
    onSuccess: (_data, { withRestart }) => {
      setRemovingIdx(null)
      invalidatePool()
      if (withRestart) restartMutation.mutate()
    },
  })

  const restartMutation = useMutation({
    mutationFn: restartApi,
    onSuccess: () => {
      setRestartMsg(t('browsers.restarting'))
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
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700"
        >
          <Plus size={15} />
          {t('browsers.addInstance')}
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
          const idx = instanceIndex(ep.url)
          return (
            <InstanceCard
              key={ep.url}
              endpoint={ep}
              isStarting={startingEndpoints.has(ep.url)}
              bindings={bindingsByEndpoint[ep.url] ?? []}
              boundSites={boundSites}
              onBind={(site) => addMutation.mutate({ browser_endpoint: ep.url, site })}
              onUnbind={(id) => deleteMutation.mutate(id)}
              onRemove={idx !== null ? () => setRemovingIdx(idx) : undefined}
              isBindPending={addMutation.isPending}
              isRemovePending={removeInstanceMutation.isPending}
              onModeChanged={invalidatePool}
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

      {/* Remove instance modal */}
      {removingIdx !== null && (
        <RemoveInstanceModal
          name={`chrome-${removingIdx}`}
          onConfirm={(withRestart) => removeInstanceMutation.mutate({ idx: removingIdx, withRestart })}
          onClose={() => { if (!removeInstanceMutation.isPending) setRemovingIdx(null) }}
          isPending={removeInstanceMutation.isPending}
        />
      )}

      {/* Add instance modal */}
      {showAddModal && (
        <AddInstanceModal
          currentCount={endpoints.length}
          onConfirm={(count, withRestart) => addInstanceMutation.mutate({ count, withRestart })}
          onClose={() => { if (!addInstanceMutation.isPending) setShowAddModal(false) }}
          isPending={addInstanceMutation.isPending}
        />
      )}
    </div>
  )
}
