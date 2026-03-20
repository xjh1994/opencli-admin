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
  onConfirm: (count: number, withRestart: boolean, mode: 'bridge' | 'cdp', nodeType: 'local' | 'agent') => void
  onClose: () => void
  isPending: boolean
}

const MODE_OPTIONS: {
  value: 'bridge' | 'cdp'
  label: string
  badge: string
  badgeCls: string
  tech: string
  desc: string
  pros: string[]
}[] = [
  {
    value: 'bridge',
    label: 'Browser Bridge 模式',
    badge: 'Bridge',
    badgeCls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    tech: 'opencli 1.0 · daemon.js + opencli Browser Bridge 扩展',
    desc: 'Chrome 内置 "opencli Browser Bridge" 扩展通过 WebSocket 连接 daemon.js 常驻进程，由 daemon 代理执行浏览器操作。Cookie、登录态由真实 Chrome 保存，容器重启不丢失。',
    pros: ['登录状态持久保留，适合需要账号的站点（B站、小红书等）', '浏览器行为接近真实用户，抗检测能力强', 'daemon 常驻保持连接，任务触发延迟低'],
  },
  {
    value: 'cdp',
    label: 'CDP 直连模式',
    badge: 'CDP',
    badgeCls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    tech: 'opencli 0.9 · Playwright 直连 Chrome DevTools Protocol',
    desc: 'API 容器通过 Playwright 直接连接 Chrome 的 DevTools Protocol 端口（:19222）控制浏览器，不经过扩展或 daemon 中转。',
    pros: ['无需扩展参与，链路更简单，故障点更少', '适合无需登录的公开页面抓取', '每次任务独立连接，状态隔离'],
  },
]

const NODE_TYPE_OPTIONS: {
  value: 'local' | 'agent'
  label: string
  badge: string
  badgeCls: string
  desc: string
}[] = [
  {
    value: 'local',
    label: '本地实例',
    badge: 'Local',
    badgeCls: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
    desc: 'Chrome 容器运行在与 API 同一个 Docker 网络中，API 直接驱动浏览器。适合单机部署。',
  },
  {
    value: 'agent',
    label: '边缘节点',
    badge: 'Agent',
    badgeCls: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
    desc: 'Chrome 运行在远程宿主机上，Agent 主动连接中心 API（WebSocket 反向通道）。适合分布式采集。',
  },
]

function AddInstanceModal({ currentCount, onConfirm, onClose, isPending }: AddInstanceModalProps) {
  const { t } = useTranslation()
  const [count, setCount] = useState(1)
  const [mode, setMode] = useState<'bridge' | 'cdp'>('bridge')
  const [nodeType, setNodeType] = useState<'local' | 'agent'>('local')

  const preview = Array.from({ length: count }, (_, i) => {
    const N = currentCount + 1 + i
    return `chrome-${N}`
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-md p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-sm font-semibold dark:text-white mb-4">{t('browsers.addInstanceTitle')}</h3>

        {/* Count picker */}
        <div className="flex items-center gap-3 mb-5">
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

        {/* Mode selector */}
        <div className="mb-5">
          <p className="text-xs font-medium text-gray-600 dark:text-gray-300 mb-2">控制模式</p>
          <div className="flex flex-col gap-2">
            {MODE_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex gap-3 cursor-pointer rounded-lg border px-3 py-3 transition-colors ${
                  mode === opt.value
                    ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-500'
                    : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                }`}
              >
                <input
                  type="radio"
                  name="instance-mode"
                  value={opt.value}
                  checked={mode === opt.value}
                  onChange={() => setMode(opt.value)}
                  className="accent-blue-600 shrink-0 mt-0.5"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium dark:text-white">{opt.label}</span>
                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${opt.badgeCls}`}>{opt.badge}</span>
                  </div>
                  <p className="text-xs font-mono text-gray-400 dark:text-gray-500 mb-1">{opt.tech}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-1.5">{opt.desc}</p>
                  <ul className="space-y-0.5">
                    {opt.pros.map((pro) => (
                      <li key={pro} className="text-xs text-gray-500 dark:text-gray-400 flex items-start gap-1">
                        <span className="text-green-500 shrink-0">✓</span>
                        {pro}
                      </li>
                    ))}
                  </ul>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Node type selector */}
        <div className="mb-5">
          <p className="text-xs font-medium text-gray-600 dark:text-gray-300 mb-2">节点类型</p>
          <div className="flex gap-2">
            {NODE_TYPE_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex-1 flex gap-2 cursor-pointer rounded-lg border px-3 py-2.5 transition-colors ${
                  nodeType === opt.value
                    ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-500'
                    : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                }`}
              >
                <input
                  type="radio"
                  name="instance-node-type"
                  value={opt.value}
                  checked={nodeType === opt.value}
                  onChange={() => setNodeType(opt.value)}
                  className="accent-blue-600 shrink-0 mt-0.5"
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="text-xs font-medium dark:text-white">{opt.label}</span>
                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${opt.badgeCls}`}>{opt.badge}</span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">{opt.desc}</p>
                </div>
              </label>
            ))}
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

        {/* Actions */}
        <div className="flex flex-col gap-2">
          <button
            onClick={() => onConfirm(count, true, mode, nodeType)}
            disabled={isPending}
            className="w-full px-3 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            {isPending ? t('browsers.adding') : t('browsers.createAndRestart')}
          </button>
          <button
            onClick={() => onConfirm(count, false, mode, nodeType)}
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
          {endpoint.node_type === 'agent' && (
            <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300">
              Agent
            </span>
          )}
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
    mutationFn: ({ count, mode, nodeType }: { count: number; withRestart: boolean; mode: 'bridge' | 'cdp'; nodeType: 'local' | 'agent' }) => addChromeInstance(count, mode, nodeType),
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
          onConfirm={(count, withRestart, mode, nodeType) => addInstanceMutation.mutate({ count, withRestart, mode, nodeType })}
          onClose={() => { if (!addInstanceMutation.isPending) setShowAddModal(false) }}
          isPending={addInstanceMutation.isPending}
        />
      )}
    </div>
  )
}
