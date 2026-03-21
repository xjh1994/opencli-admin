import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  listNodes,
  getNodeEvents,
  getNodeStats,
  deleteNode,
  listBrowserBindings,
  createBrowserBinding,
  deleteBrowserBinding,
  getChromePool,
  updateChromeEndpointMode,
  updateChromeInstanceConfig,
  getSystemConfig,
  updateSystemConfig,
  getWsAgentStatus,
  restartApi,
} from '../api/endpoints'
import type { EdgeNode, EdgeNodeEvent, BrowserBinding, ChromeEndpoint } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import PageHeader from '../components/PageHeader'
import { SITE_LABELS } from '../components/ChannelConfigForm'
import {
  Plus, Trash2, ChevronDown, ChevronUp, Copy, Check, RefreshCw,
  X, ExternalLink, Wifi, WifiOff,
} from 'lucide-react'

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} 小时前`
  return `${Math.floor(h / 24)} 天前`
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

function instanceLabel(cdpUrl: string): string {
  return cdpUrl.replace('http://', '').replace(':19222', '')
}

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

const inputCls =
  'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'

// ── Install Wizard Modal ──────────────────────────────────────────────────────

type InstallMethod = 'docker' | 'shell'
type RegisterMode = 'ws' | 'http'
type AgentMode = 'bridge' | 'cdp'
type DockerNetwork = 'bridge' | 'host'
function InstallWizardModal({ onClose, agentImageTag }: { onClose: () => void; agentImageTag: string }) {
  const [method, setMethod] = useState<InstallMethod>('docker')
  const [regMode, setRegMode] = useState<RegisterMode>('ws')
  const [agentMode, setAgentMode] = useState<AgentMode>('bridge')
  const [dockerNetwork, setDockerNetwork] = useState<DockerNetwork>('bridge')
  const [installChrome, setInstallChrome] = useState(false)
  const [copied, setCopied] = useState(false)

  const origin = window.location.origin
  const imageTag = installChrome ? `${agentImageTag}-chrome` : agentImageTag

  const cmd = (() => {
    if (method === 'shell') {
      const envPrefix = `AGENT_REGISTER=${regMode} AGENT_MODE=${agentMode}`
      return `curl -fsSL ${origin}/api/v1/nodes/install/agent.sh | \\\n  ${envPrefix} bash -s -- python`
    }
    const useHost = dockerNetwork === 'host'
    const lines = [
      'docker run -d \\',
      '  --name opencli-agent \\',
      '  --restart unless-stopped \\',
    ]
    if (useHost) {
      lines.push('  --network host \\')
    } else {
      lines.push('  --add-host=host.docker.internal:host-gateway \\')
    }
    lines.push(`  -e CENTRAL_API_URL=${origin} \\`)
    lines.push(`  -e AGENT_REGISTER=${regMode} \\`)
    lines.push(`  -e AGENT_MODE=${agentMode} \\`)
    lines.push('  -e AGENT_DEPLOY_TYPE=docker \\')
    if (!useHost) {
      lines.push('  -p 19823:19823 \\')
    }
    lines.push(`  xjh1994/opencli-admin-agent:${imageTag}`)
    return lines.join('\n')
  })()

  const regModeHint: Record<RegisterMode, string> = {
    ws: 'WS 反向通道：Agent 主动连接中心，适合 NAT / 跨网场景，无需开放入站端口。',
    http: 'HTTP 直连：中心主动请求 Agent，适合局域网场景，Agent 需对中心可访问。',
  }
  const agentModeHint: Record<AgentMode, string> = {
    bridge: 'Bridge（推荐）：opencli 通过 Daemon 连接 Chrome，速度快、稳定。',
    cdp: 'CDP：opencli 通过 CDP 协议直连 Chrome，适合兼容性场景。',
  }

  const reset = () => setCopied(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(cmd).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const tabCls = (active: boolean) =>
    [
      'px-4 py-2.5 text-sm font-medium transition-colors border-b-2',
      active
        ? 'border-blue-600 text-blue-600 dark:text-blue-400'
        : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300',
    ].join(' ')

  const btnCls = (active: boolean) =>
    [
      'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
      active
        ? 'bg-blue-600 text-white'
        : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600',
    ].join(' ')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-5 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-base font-semibold dark:text-white">新增节点</h2>
        </div>
        <div className="flex border-b border-gray-100 dark:border-gray-700">
          <button className={tabCls(method === 'docker')} onClick={() => { setMethod('docker'); reset() }}>
            Docker 直接运行
          </button>
          <button className={tabCls(method === 'shell')} onClick={() => { setMethod('shell'); reset() }}>
            Shell 脚本
          </button>
        </div>
        <div className="p-5 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500 dark:text-gray-400 w-16 shrink-0">注册模式</span>
            <div className="flex gap-1.5">
              <button className={btnCls(regMode === 'ws')} onClick={() => { setRegMode('ws'); reset() }}>WS 反向通道</button>
              <button className={btnCls(regMode === 'http')} onClick={() => { setRegMode('http'); reset() }}>HTTP 直连</button>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500 dark:text-gray-400 w-16 shrink-0">采集模式</span>
            <div className="flex gap-1.5">
              <button className={btnCls(agentMode === 'bridge')} onClick={() => { setAgentMode('bridge'); reset() }}>Bridge</button>
              <button className={btnCls(agentMode === 'cdp')} onClick={() => { setAgentMode('cdp'); reset() }}>CDP</button>
            </div>
          </div>
          {method === 'docker' && (
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 dark:text-gray-400 w-16 shrink-0">网络模式</span>
              <div className="flex gap-1.5">
                <button className={btnCls(dockerNetwork === 'bridge')} onClick={() => { setDockerNetwork('bridge'); reset() }}>Bridge（默认）</button>
                <button className={btnCls(dockerNetwork === 'host')} onClick={() => { setDockerNetwork('host'); reset() }}>Host（Linux）</button>
              </div>
            </div>
          )}
          {method === 'docker' && (
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 dark:text-gray-400 w-16 shrink-0">Chrome</span>
              <div className="flex gap-1.5">
                <button className={btnCls(!installChrome)} onClick={() => { setInstallChrome(false); reset() }}>宿主机 Chrome（~100 MB）</button>
                <button className={btnCls(installChrome)} onClick={() => { setInstallChrome(true); reset() }}>内置 Chrome（~450 MB）</button>
              </div>
            </div>
          )}
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg px-3 py-2 text-xs text-blue-700 dark:text-blue-300 space-y-1">
            <p>{regModeHint[regMode]}</p>
            <p>{agentModeHint[agentMode]}</p>
            {method === 'docker' && dockerNetwork === 'host' && (
              <p>Host 网络：容器直接使用宿主机网络，无需端口映射，适合 API 运行在宿主机（非 Docker）时使用。仅 Linux 支持。</p>
            )}
            {method === 'docker' && (installChrome
              ? <p>内置 Chrome：镜像自包含 Chromium + Xvfb，无需宿主机提供 Chrome。</p>
              : <p>宿主机 Chrome：使用轻量镜像（~100 MB），连接宿主机 Chrome（需提前启动并开启 CDP 端口 9222）。</p>
            )}
            {method === 'shell' && (
              <p>Shell 脚本：无需 Docker，脚本自动安装 Python 依赖并启动 Agent，有 systemd 时注册为服务。</p>
            )}
          </div>
          <div className="relative">
            <pre className="bg-gray-900 text-gray-100 rounded-lg px-4 py-3 text-xs font-mono overflow-x-auto whitespace-pre">{cmd}</pre>
            <button
              onClick={handleCopy}
              className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 rounded text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? '已复制' : '复制'}
            </button>
          </div>
        </div>
        <div className="p-5 border-t border-gray-100 dark:border-gray-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Node Event Timeline ───────────────────────────────────────────────────────

function NodeEventTimeline({ nodeId }: { nodeId: string }) {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: ['node-events', nodeId],
    queryFn: () => getNodeEvents(nodeId),
  })
  const events: EdgeNodeEvent[] = data?.data ?? []

  const eventLabel = (event: EdgeNodeEvent['event']) => {
    if (event === 'registered') return t('browsers.eventRegistered')
    if (event === 'online') return t('browsers.eventOnline')
    return t('browsers.eventOffline')
  }
  const eventDot = (event: EdgeNodeEvent['event']) => {
    if (event === 'registered') return 'bg-blue-500'
    if (event === 'online') return 'bg-green-500'
    return 'bg-gray-400'
  }

  if (isLoading) return <div className="mt-3 text-xs text-gray-400">{t('common.loading')}</div>
  if (events.length === 0) return <div className="mt-3 text-xs text-gray-400">{t('common.noData')}</div>

  return (
    <div className="mt-3 space-y-2">
      {events.map((ev) => (
        <div key={ev.id} className="flex items-start gap-2.5">
          <span className={`w-2 h-2 rounded-full mt-0.5 shrink-0 ${eventDot(ev.event)}`} />
          <div className="flex-1 min-w-0">
            <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{eventLabel(ev.event)}</span>
            {ev.ip && <span className="ml-2 text-xs text-gray-400 font-mono">{ev.ip}</span>}
          </div>
          <span className="text-xs text-gray-400 shrink-0">{timeAgo(ev.created_at)}</span>
        </div>
      ))}
    </div>
  )
}

// ── Node Stats Panel ──────────────────────────────────────────────────────────

type StatRange = 'today' | 'yesterday' | '7d' | '30d' | 'all'
const STAT_RANGE_LABELS: Record<StatRange, string> = {
  today: '今天', yesterday: '昨天', '7d': '7 天', '30d': '30 天', all: '全部',
}

function NodeStatsPanel({ nodeId }: { nodeId: string }) {
  const [range, setRange] = useState<StatRange>('7d')
  const { data, isLoading } = useQuery({
    queryKey: ['node-stats', nodeId, range],
    queryFn: () => getNodeStats(nodeId, { range }),
  })
  const ranges: StatRange[] = ['today', 'yesterday', '7d', '30d', 'all']

  return (
    <div className="mt-3 space-y-2">
      <div className="flex gap-1 flex-wrap">
        {ranges.map((r) => (
          <button
            key={r}
            onClick={() => setRange(r)}
            className={[
              'px-2 py-0.5 rounded text-xs font-medium transition-colors',
              range === r
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600',
            ].join(' ')}
          >
            {STAT_RANGE_LABELS[r]}
          </button>
        ))}
      </div>
      {isLoading ? (
        <p className="text-xs text-gray-400">加载中…</p>
      ) : data ? (
        <div className="grid grid-cols-4 gap-2">
          {[
            { label: '总执行', value: data.total },
            { label: '成功', value: data.success, cls: 'text-green-600 dark:text-green-400' },
            { label: '失败', value: data.failed, cls: 'text-red-500 dark:text-red-400' },
            { label: '成功率', value: `${data.success_rate}%`, cls: 'text-blue-600 dark:text-blue-400' },
          ].map(({ label, value, cls }) => (
            <div key={label} className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-2 text-center">
              <p className="text-xs text-gray-400 mb-0.5">{label}</p>
              <p className={`text-sm font-semibold ${cls ?? 'text-gray-800 dark:text-gray-100'}`}>{value}</p>
            </div>
          ))}
        </div>
      ) : null}
      {data && data.total > 0 && (
        <p className="text-xs text-gray-400">累计采集 {data.records_collected} 条记录</p>
      )}
    </div>
  )
}

// ── Node Card ─────────────────────────────────────────────────────────────────

interface NodeCardProps {
  node: EdgeNode
  wsConnectedSet: Set<string>
  onDelete: () => void
  isDeletePending: boolean
}

function NodeCard({ node, wsConnectedSet, onDelete, isDeletePending }: NodeCardProps) {
  const { t } = useTranslation()
  const [panel, setPanel] = useState<'none' | 'stats' | 'history'>('none')
  const isWs = node.protocol === 'ws'
  const isOnline = node.status === 'online' || (isWs && wsConnectedSet.has(node.url))

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-800 p-4">
      <div className="flex items-start gap-3">
        <span
          className={`mt-1 w-2.5 h-2.5 rounded-full shrink-0 ${isOnline ? 'bg-green-500' : 'bg-gray-400'}`}
          title={isOnline ? '在线' : '离线'}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-gray-900 dark:text-white truncate max-w-[200px]" title={node.url}>
              {node.url}
            </span>
            {node.label && node.label !== node.url && (
              <span className="text-xs text-gray-400">({node.label})</span>
            )}
            <span className={[
              'px-1.5 py-0.5 rounded text-xs font-medium',
              isWs
                ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300'
                : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
            ].join(' ')}>
              {isWs ? t('browsers.protocolWs') : t('browsers.protocolHttp')}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className={[
              'px-1.5 py-0.5 rounded text-xs font-medium',
              node.node_type === 'shell'
                ? 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
            ].join(' ')}>
              {node.node_type === 'shell' ? 'Shell' : 'Docker'}
            </span>
            <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
              {node.mode}
            </span>
            {node.ip && <span className="text-xs text-gray-400 font-mono">{node.ip}</span>}
            <span className={`text-xs font-medium ${isOnline ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}`}>
              {isOnline ? '● 在线' : '○ 离线'}
            </span>
            <span className="text-xs text-gray-400">
              {t('browsers.lastSeen')}: {node.last_seen_at ? timeAgo(node.last_seen_at) : t('browsers.never')}
            </span>
          </div>
          {panel === 'history' && <NodeEventTimeline nodeId={node.id} />}
          {panel === 'stats' && <NodeStatsPanel nodeId={node.id} />}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setPanel((v) => (v === 'stats' ? 'none' : 'stats'))}
            className={[
              'flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors',
              panel === 'stats'
                ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700',
            ].join(' ')}
          >
            {panel === 'stats' ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            统计
          </button>
          <button
            onClick={() => setPanel((v) => (v === 'history' ? 'none' : 'history'))}
            className={[
              'flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors',
              panel === 'history'
                ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700',
            ].join(' ')}
          >
            {panel === 'history' ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {t('browsers.eventHistory')}
          </button>
          <button
            onClick={onDelete}
            disabled={isDeletePending}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Site Dropdown ─────────────────────────────────────────────────────────────

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

// ── Status Badge (Docker container) ──────────────────────────────────────────

function StatusBadge({ containerStatus, available, isStarting }: {
  containerStatus?: string; available: boolean; isStarting?: boolean
}) {
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
    return available ? (
      <span className="inline-flex items-center gap-1 text-xs">
        <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
        <span className="text-green-600 dark:text-green-400">{t('browsers.statusIdle')}</span>
      </span>
    ) : (
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
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse shrink-0" />
      <span className="text-yellow-600 dark:text-yellow-400">{t('browsers.statusPending')}</span>
    </span>
  )
}

// ── Mode Toggle ───────────────────────────────────────────────────────────────

function ModeToggle({ endpoint, onSuccess, isDockerEndpoint }: {
  endpoint: ChromeEndpoint; onSuccess: () => void; isDockerEndpoint: boolean
}) {
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
    <div className="flex flex-col items-end gap-1">
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
                ? m === 'bridge' ? 'bg-blue-600 text-white' : 'bg-amber-500 text-white'
                : 'bg-white dark:bg-gray-800 text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700',
            ].join(' ')}
          >
            {t(`workers.mode${m.charAt(0).toUpperCase() + m.slice(1)}`)}
          </button>
        ))}
      </div>
      {!isDockerEndpoint && mode === 'cdp' && (
        <span className="text-xs text-amber-600 dark:text-amber-400 whitespace-nowrap">
          ⚠ CDP 会启动新 Chrome，本地请用 Bridge
        </span>
      )}
    </div>
  )
}

// ── Instance Card (Chrome pool endpoint) ──────────────────────────────────────

interface InstanceCardProps {
  endpoint: ChromeEndpoint
  isStarting?: boolean
  wsConnected?: boolean
  bindings: BrowserBinding[]
  boundSites: Set<string>
  onBind: (site: string) => void
  onUnbind: (id: string) => void
  onRemove?: () => void
  isBindPending: boolean
  isRemovePending: boolean
  onModeChanged: () => void
  onConfigChanged: () => void
  showModeToggle?: boolean
}

function InstanceCard({
  endpoint, isStarting, wsConnected, bindings, boundSites,
  onBind, onUnbind, onRemove, isBindPending, isRemovePending, onModeChanged, onConfigChanged,
  showModeToggle = false,
}: InstanceCardProps) {
  const { t } = useTranslation()
  const { url, available, container_status: containerStatus, novnc_port: novncPort } = endpoint
  const [editingAgentUrl, setEditingAgentUrl] = useState(false)
  const [agentUrlDraft, setAgentUrlDraft] = useState(endpoint.agent_url ?? '')
  const [agentProtocolDraft, setAgentProtocolDraft] = useState<'http' | 'ws'>(endpoint.agent_protocol === 'ws' ? 'ws' : 'http')

  const saveAgentUrlMutation = useMutation({
    mutationFn: ({ agent_url, agent_protocol }: { agent_url: string; agent_protocol: string }) =>
      updateChromeInstanceConfig(url, { agent_url: agent_url || null, agent_protocol: agent_protocol || null }),
    onSuccess: () => { setEditingAgentUrl(false); onConfigChanged() },
  })

  const novncUrl = `http://${window.location.hostname}:${novncPort}`
  const label = instanceLabel(url)
  const idx = instanceIndex(url)
  const isDockerEndpoint = idx !== null
  const canRemove = isDockerEndpoint && idx > 1 && onRemove

  return (
    <Card>
      <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-100 dark:border-gray-700">
        {isDockerEndpoint
          ? <StatusBadge containerStatus={containerStatus} available={available} isStarting={isStarting} />
          : <span className={`inline-flex items-center gap-1 text-xs ${available ? 'text-green-500' : 'text-gray-400'}`}>
              <span className={`w-2 h-2 rounded-full shrink-0 ${available ? 'bg-green-500' : 'bg-gray-400'}`} />
              {available ? '在线' : '空闲'}
            </span>
        }
        <span className="font-semibold text-sm dark:text-white">
          {isDockerEndpoint ? label : '本地 Chrome'}
        </span>
        {!isDockerEndpoint && <span className="text-xs text-gray-400 font-mono">{label}</span>}
        {isDockerEndpoint && (
          <a
            href={novncUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-blue-500 hover:underline font-mono"
          >
            :{novncPort ?? chromeNovncPort(url)}
            <ExternalLink size={11} />
          </a>
        )}
        <div className="ml-auto flex items-center gap-2">
          {endpoint.agent_protocol === 'ws' && (wsConnected ? (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300">
              <Wifi size={10} />{t('browsers.statusWsConnected')}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400">
              <WifiOff size={10} />{t('browsers.statusWsOffline')}
            </span>
          ))}
          {!!endpoint.agent_url && endpoint.agent_protocol === 'http' && (
            <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300">
              HTTP Agent
            </span>
          )}
          {showModeToggle && <ModeToggle endpoint={endpoint} onSuccess={onModeChanged} isDockerEndpoint={isDockerEndpoint} />}
          {canRemove && (
            <button
              onClick={onRemove}
              disabled={isRemovePending}
              className="text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Agent URL row */}
      <div className="mb-3 pb-3 border-b border-gray-100 dark:border-gray-700">
        {editingAgentUrl ? (
          <div className="space-y-2">
            <input
              autoFocus
              type="url"
              value={agentUrlDraft}
              onChange={(e) => setAgentUrlDraft(e.target.value)}
              placeholder="http://192.168.1.100:19823"
              className="w-full px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
            />
            {agentUrlDraft && (
              <div className="flex gap-2">
                {(['http', 'ws'] as const).map((p) => (
                  <label key={p} className={`flex items-center gap-1.5 px-2 py-1 rounded border cursor-pointer text-xs transition-colors ${
                    agentProtocolDraft === p
                      ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                      : 'border-gray-200 dark:border-gray-600 text-gray-500 hover:border-gray-300'
                  }`}>
                    <input type="radio" name={`protocol-${url}`} value={p} checked={agentProtocolDraft === p}
                      onChange={() => setAgentProtocolDraft(p)} className="accent-blue-600" />
                    {p === 'http' ? 'HTTP（局域网 / 代理）' : 'WS（反向连接）'}
                  </label>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={() => saveAgentUrlMutation.mutate({ agent_url: agentUrlDraft, agent_protocol: agentProtocolDraft })}
                disabled={saveAgentUrlMutation.isPending}
                className="px-2 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              >保存</button>
              <button
                onClick={() => { setEditingAgentUrl(false); setAgentUrlDraft(endpoint.agent_url ?? ''); setAgentProtocolDraft(endpoint.agent_protocol === 'ws' ? 'ws' : 'http') }}
                className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700"
              >取消</button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => { setAgentUrlDraft(endpoint.agent_url ?? ''); setAgentProtocolDraft(endpoint.agent_protocol === 'ws' ? 'ws' : 'http'); setEditingAgentUrl(true) }}
            className="flex items-center gap-1.5 text-xs group"
          >
            <span className="text-gray-400 shrink-0">Agent:</span>
            {endpoint.agent_url ? (
              <>
                <span className="font-mono text-blue-600 dark:text-blue-400 group-hover:underline truncate max-w-[160px]">{endpoint.agent_url}</span>
                <span className="px-1 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 font-mono">{endpoint.agent_protocol ?? 'http'}</span>
              </>
            ) : (
              <span className="text-gray-400 italic group-hover:text-blue-500">未配置 — 点击设置</span>
            )}
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

function SwitchModeModal({ target, onConfirm, onClose, isPending }: {
  target: 'local' | 'agent'
  onConfirm: () => void
  onClose: () => void
  isPending: boolean
}) {
  const info = target === 'local'
    ? {
        title: '切换为本地模式',
        desc: '切换后，所有采集任务将直连本地 Chrome，不再通过 Agent 节点路由。',
        warn: '已注册的 Agent 节点不会被删除，切换回 Agent 模式后仍可继续使用。',
        btnCls: 'bg-blue-600 hover:bg-blue-700',
        btnLabel: '切换为本地模式',
      }
    : {
        title: '切换为 Agent 模式',
        desc: '切换后，采集任务将通过已注册的 Agent 节点执行。',
        warn: '请确保至少有一个 Agent 节点在线，否则采集任务将失败。',
        btnCls: 'bg-purple-600 hover:bg-purple-700',
        btnLabel: '切换为 Agent 模式',
      }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-sm p-5" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-semibold dark:text-white mb-2">{info.title}</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">{info.desc}</p>
        <div className="flex items-start gap-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg px-3 py-2.5 mb-5">
          <span className="text-amber-500 shrink-0 mt-0.5">⚠</span>
          <p className="text-xs text-amber-700 dark:text-amber-300">{info.warn}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onConfirm}
            disabled={isPending}
            className={`flex-1 px-3 py-2 text-sm rounded-lg text-white font-medium disabled:opacity-50 ${info.btnCls}`}
          >
            {isPending ? '切换中…' : info.btnLabel}
          </button>
          <button
            onClick={onClose}
            disabled={isPending}
            className="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  )
}

export default function NodesPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showWizard, setShowWizard] = useState(false)
  const [pendingMode, setPendingMode] = useState<'local' | 'agent' | null>(null)
  const [restartMsg, setRestartMsg] = useState<string | null>(null)

  // ── Queries ──
  const { data: sysConfig } = useQuery({ queryKey: ['system-config'], queryFn: getSystemConfig })
  const { data: wsStatus } = useQuery({ queryKey: ['ws-agent-status'], queryFn: getWsAgentStatus, refetchInterval: 10_000 })
  const wsConnectedSet = new Set(wsStatus?.connected ?? [])

  const { data: poolData, isLoading: poolLoading, error: poolError, refetch: refetchPool } = useQuery({
    queryKey: ['chrome-pool'],
    queryFn: getChromePool,
    refetchInterval: 10_000,
  })
  const { data: nodesData, isLoading: nodesLoading, error: nodesError, refetch: refetchNodes } = useQuery({
    queryKey: ['nodes'],
    queryFn: listNodes,
    refetchInterval: 10_000,
  })
  const { data: bindingsData } = useQuery({ queryKey: ['browser-bindings'], queryFn: listBrowserBindings })

  const endpoints: ChromeEndpoint[] = poolData?.endpoints ?? []
  const nodes: EdgeNode[] = nodesData?.data ?? []
  const bindings: BrowserBinding[] = bindingsData?.data ?? []

  const localEndpoints = endpoints.filter((ep) => instanceIndex(ep.url) === null)

  const bindingsByEndpoint: Record<string, BrowserBinding[]> = {}
  for (const ep of localEndpoints) bindingsByEndpoint[ep.url] = []
  for (const b of bindings) {
    if (bindingsByEndpoint[b.browser_endpoint] !== undefined)
      bindingsByEndpoint[b.browser_endpoint].push(b)
  }
  const boundSites = new Set(bindings.map((b) => b.site))

  const invalidatePool = () => {
    qc.invalidateQueries({ queryKey: ['chrome-pool'] })
    qc.invalidateQueries({ queryKey: ['browser-bindings'] })
  }

  // ── Mutations ──
  const switchModeMut = useMutation({
    mutationFn: (mode: 'local' | 'agent') => updateSystemConfig({ collection_mode: mode }),
    onSuccess: (newConfig) => { qc.setQueryData(['system-config'], newConfig); toast.success('采集模式已切换') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '切换失败'),
  })

  const restartMut = useMutation({
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

  const deleteNodeMut = useMutation({
    mutationFn: deleteNode,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['nodes'] }); toast.success('节点已删除') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '删除失败'),
  })

  const addBindingMut = useMutation({
    mutationFn: createBrowserBinding,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['browser-bindings'] }); toast.success('站点绑定已添加') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '绑定失败'),
  })

  const deleteBindingMut = useMutation({
    mutationFn: deleteBrowserBinding,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['browser-bindings'] }); toast.success('已解绑') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '解绑失败'),
  })

  if (poolLoading || nodesLoading) return <PageLoader />
  if (poolError) return <ErrorAlert error={poolError as Error} onRetry={refetchPool} />
  if (nodesError) return <ErrorAlert error={nodesError as Error} onRetry={refetchNodes} />

  const collectionMode = sysConfig?.collection_mode ?? 'local'

  return (
    <div>
      <PageHeader title={t('browsers.title')} description={t('browsers.description')} />

      {/* ── 采集模式 ── */}
      {sysConfig && (
        <div className="mb-6 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
            <div>
              <span className="text-sm font-semibold text-gray-800 dark:text-white">{t('browsers.collectionMode')}</span>
              <span className="ml-2 text-xs text-gray-400">切换后立即生效，影响所有任务的采集路由</span>
            </div>
            <button
              onClick={() => restartMut.mutate()}
              disabled={restartMut.isPending || !!restartMsg}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
            >
              <RefreshCw size={13} className={restartMsg ? 'animate-spin' : ''} />
              {restartMsg ?? t('browsers.restartApi')}
            </button>
          </div>
          <div className="p-4 grid grid-cols-2 gap-3">
            {([
              {
                value: 'local' as const,
                label: '本地模式',
                desc: '中心直连本地 Chrome（shell 部署），不经过 Agent。适合单机开发或简单采集场景。',
                activeCls: 'border-blue-500 bg-blue-50 dark:bg-blue-900/20',
                dotCls: 'bg-blue-500',
              },
              {
                value: 'agent' as const,
                label: 'Agent 模式',
                desc: '通过 Agent 节点采集，支持本地 Docker 容器或远端多机分布式部署。',
                activeCls: 'border-purple-500 bg-purple-50 dark:bg-purple-900/20',
                dotCls: 'bg-purple-500',
              },
            ] as const).map(({ value, label, desc, activeCls, dotCls }) => {
              const isActive = sysConfig.collection_mode === value
              return (
                <button
                  key={value}
                  disabled={switchModeMut.isPending}
                  onClick={() => !isActive && setPendingMode(value)}
                  className={[
                    'flex items-start gap-3 text-left rounded-lg border-2 px-4 py-3 transition-colors',
                    isActive ? activeCls : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500',
                  ].join(' ')}
                >
                  <span className={`mt-1 w-3 h-3 rounded-full shrink-0 border-2 ${isActive ? `${dotCls} border-transparent` : 'border-gray-300 dark:border-gray-600'}`} />
                  <div className="min-w-0">
                    <p className={`text-sm font-semibold ${isActive ? 'text-gray-900 dark:text-white' : 'text-gray-500 dark:text-gray-400'}`}>{label}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">{desc}</p>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── 本地模式：直连本地 Chrome ── */}
      {collectionMode === 'local' && (
        <div>
          {localEndpoints.length === 0 ? (
            <div className="text-center py-12 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl">
              <p className="text-sm text-gray-500">未检测到本地浏览器端点</p>
              <p className="text-xs text-gray-400 mt-1">请确保 Chrome 以调试模式启动（Bridge 或 CDP）</p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {localEndpoints.map((ep) => (
                <InstanceCard
                  key={ep.url}
                  endpoint={ep}
                  bindings={bindingsByEndpoint[ep.url] ?? []}
                  boundSites={boundSites}
                  onBind={(site) => addBindingMut.mutate({ browser_endpoint: ep.url, site })}
                  onUnbind={(id) => deleteBindingMut.mutate(id)}
                  isBindPending={addBindingMut.isPending}
                  isRemovePending={false}
                  onModeChanged={invalidatePool}
                  onConfigChanged={invalidatePool}
                  showModeToggle
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Agent 模式：节点列表 ── */}
      {collectionMode === 'agent' && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-base font-semibold text-gray-800 dark:text-white">Agent 节点</h2>
              <p className="text-xs text-gray-500 mt-0.5">已注册的 Agent 节点（本地或远端）</p>
            </div>
            <button
              onClick={() => setShowWizard(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700"
            >
              <Plus size={14} />
              {t('browsers.addNode')}
            </button>
          </div>
          {nodes.length === 0 ? (
            <div className="text-center py-12 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl">
              <p className="text-sm text-gray-500">{t('browsers.noNodes')}</p>
              <p className="text-xs text-gray-400 mt-1">{t('browsers.noNodesHint')}</p>
              <button
                onClick={() => setShowWizard(true)}
                className="mt-4 flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm bg-blue-600 text-white hover:bg-blue-700 mx-auto"
              >
                <Plus size={14} />
                {t('browsers.addNode')}
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {nodes.map((node) => (
                <NodeCard
                  key={node.id}
                  node={node}
                  wsConnectedSet={wsConnectedSet}
                  onDelete={() => {
                    if (confirm(t('browsers.confirmDeleteNode', { url: node.url }))) {
                      deleteNodeMut.mutate(node.id)
                    }
                  }}
                  isDeletePending={deleteNodeMut.isPending}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {showWizard && <InstallWizardModal onClose={() => setShowWizard(false)} agentImageTag={sysConfig?.image_tag ?? 'latest'} />}
      {pendingMode && (
        <SwitchModeModal
          target={pendingMode}
          onConfirm={() => { switchModeMut.mutate(pendingMode); setPendingMode(null) }}
          onClose={() => { if (!switchModeMut.isPending) setPendingMode(null) }}
          isPending={switchModeMut.isPending}
        />
      )}
    </div>
  )
}
