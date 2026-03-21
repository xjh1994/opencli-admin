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
  getSystemConfig,
  updateSystemConfig,
  getWsAgentStatus,
  restartApi,
} from '../api/endpoints'
import type { EdgeNode, EdgeNodeEvent, BrowserBinding, NodeStats } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import PageHeader from '../components/PageHeader'
import { SITE_LABELS } from '../components/ChannelConfigForm'
import { Plus, Trash2, ChevronDown, ChevronUp, Copy, Check, RefreshCw, X } from 'lucide-react'

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

const inputCls =
  'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'

// ── Install Wizard Modal ──────────────────────────────────────────────────────

type InstallMethod = 'docker' | 'shell'
type RegisterMode = 'ws' | 'http'
type AgentMode = 'bridge' | 'cdp'
type DockerNetwork = 'bridge' | 'host'

function InstallWizardModal({ onClose }: { onClose: () => void }) {
  const [method, setMethod] = useState<InstallMethod>('docker')
  const [regMode, setRegMode] = useState<RegisterMode>('ws')
  const [agentMode, setAgentMode] = useState<AgentMode>('bridge')
  const [dockerNetwork, setDockerNetwork] = useState<DockerNetwork>('bridge')
  const [copied, setCopied] = useState(false)

  const origin = window.location.origin

  const cmd = (() => {
    if (method === 'docker') {
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
      lines.push('  xjh1994/opencli-admin-agent:0.3.0')
      return lines.join('\n')
    }
    // shell
    const envPrefix = `AGENT_REGISTER=${regMode} AGENT_MODE=${agentMode} AGENT_DEPLOY_TYPE=shell`
    return `curl -fsSL ${origin}/api/v1/nodes/install/agent.sh | ${envPrefix} bash`
  })()

  const regModeHint: Record<RegisterMode, string> = {
    ws: 'WS 反向通道：Agent 主动连接中心，适合 NAT / 跨网场景，无需开放入站端口。',
    http: 'HTTP 直连：中心主动请求 Agent，适合局域网场景，Agent 需对中心可访问。',
  }

  const agentModeHint: Record<AgentMode, string> = {
    bridge: 'Bridge（推荐）：opencli 通过 Daemon 连接 Chrome，速度快、稳定。',
    cdp: 'CDP：opencli 通过 CDP 协议直连 Chrome，适合兼容性场景。',
  }

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
        {/* Header */}
        <div className="p-5 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-base font-semibold dark:text-white">新增节点</h2>
        </div>

        {/* Method tabs */}
        <div className="flex border-b border-gray-100 dark:border-gray-700">
          <button className={tabCls(method === 'docker')} onClick={() => { setMethod('docker'); setCopied(false) }}>
            Docker
          </button>
          <button className={tabCls(method === 'shell')} onClick={() => { setMethod('shell'); setCopied(false) }}>
            Shell 脚本
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Register mode */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500 dark:text-gray-400 w-16 shrink-0">注册模式</span>
            <div className="flex gap-1.5">
              <button className={btnCls(regMode === 'ws')} onClick={() => { setRegMode('ws'); setCopied(false) }}>
                WS 反向通道
              </button>
              <button className={btnCls(regMode === 'http')} onClick={() => { setRegMode('http'); setCopied(false) }}>
                HTTP 直连
              </button>
            </div>
          </div>

          {/* Agent (collection) mode */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500 dark:text-gray-400 w-16 shrink-0">采集模式</span>
            <div className="flex gap-1.5">
              <button className={btnCls(agentMode === 'bridge')} onClick={() => { setAgentMode('bridge'); setCopied(false) }}>
                Bridge
              </button>
              <button className={btnCls(agentMode === 'cdp')} onClick={() => { setAgentMode('cdp'); setCopied(false) }}>
                CDP
              </button>
            </div>
          </div>

          {/* Docker network mode */}
          {method === 'docker' && (
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 dark:text-gray-400 w-16 shrink-0">网络模式</span>
              <div className="flex gap-1.5">
                <button className={btnCls(dockerNetwork === 'bridge')} onClick={() => { setDockerNetwork('bridge'); setCopied(false) }}>
                  Bridge（默认）
                </button>
                <button className={btnCls(dockerNetwork === 'host')} onClick={() => { setDockerNetwork('host'); setCopied(false) }}>
                  Host（Linux）
                </button>
              </div>
            </div>
          )}

          {/* Hints */}
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg px-3 py-2 text-xs text-blue-700 dark:text-blue-300 space-y-1">
            <p>{regModeHint[regMode]}</p>
            <p>{agentModeHint[agentMode]}</p>
            {method === 'docker' && dockerNetwork === 'host' && (
              <p>Host 网络：容器直接使用宿主机网络，无需端口映射，适合 API 运行在宿主机（非 Docker）时使用。仅 Linux 支持。</p>
            )}
          </div>

          {/* Command block */}
          <div className="relative">
            <pre className="bg-gray-900 text-gray-100 rounded-lg px-4 py-3 text-xs font-mono overflow-x-auto whitespace-pre">
              {cmd}
            </pre>
            <button
              onClick={handleCopy}
              className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 rounded text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? '已复制' : '复制'}
            </button>
          </div>

          {method === 'shell' && (
            <p className="text-xs text-gray-400">
              在目标机器上执行上述命令。需要 Python 3 环境；无 Docker 时自动安装依赖并后台运行。
            </p>
          )}
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

// ── Node Events Timeline ──────────────────────────────────────────────────────

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

  if (isLoading) {
    return <div className="mt-3 text-xs text-gray-400">{t('common.loading')}</div>
  }

  if (events.length === 0) {
    return <div className="mt-3 text-xs text-gray-400">{t('common.noData')}</div>
  }

  return (
    <div className="mt-3 space-y-2">
      {events.map((ev) => (
        <div key={ev.id} className="flex items-start gap-2.5">
          <span className={`w-2 h-2 rounded-full mt-0.5 shrink-0 ${eventDot(ev.event)}`} />
          <div className="flex-1 min-w-0">
            <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{eventLabel(ev.event)}</span>
            {ev.ip && (
              <span className="ml-2 text-xs text-gray-400 font-mono">{ev.ip}</span>
            )}
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
  today: '今天',
  yesterday: '昨天',
  '7d': '7 天',
  '30d': '30 天',
  all: '全部',
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
      {/* Range selector */}
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

      {/* Stats */}
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
        {/* Status dot */}
        <span
          className={`mt-1 w-2.5 h-2.5 rounded-full shrink-0 ${isOnline ? 'bg-green-500' : 'bg-gray-400'}`}
          title={isOnline ? '在线' : '离线'}
        />

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-gray-900 dark:text-white truncate max-w-[200px]" title={node.url}>
              {node.url}
            </span>
            {node.label && node.label !== node.url && (
              <span className="text-xs text-gray-400">({node.label})</span>
            )}
            <span
              className={[
                'px-1.5 py-0.5 rounded text-xs font-medium',
                isWs
                  ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300'
                  : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
              ].join(' ')}
            >
              {isWs ? t('browsers.protocolWs') : t('browsers.protocolHttp')}
            </span>
          </div>

          <div className="flex items-center gap-2 mt-1 flex-wrap">
            {/* Deployment type badge: shell (native process) | docker (container) */}
            <span className={[
              'px-1.5 py-0.5 rounded text-xs font-medium',
              node.node_type === 'shell'
                ? 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
            ].join(' ')}>
              {node.node_type === 'shell' ? 'Shell' : 'Docker'}
            </span>
            {/* Chrome connection mode badge: bridge | cdp */}
            <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
              {node.mode}
            </span>
            {node.ip && (
              <span className="text-xs text-gray-400 font-mono">{node.ip}</span>
            )}
            <span className={`text-xs font-medium ${isOnline ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}`}>
              {isOnline ? '● 在线' : '○ 离线'}
            </span>
            <span className="text-xs text-gray-400">
              {t('browsers.lastSeen')}:{' '}
              {node.last_seen_at ? timeAgo(node.last_seen_at) : t('browsers.never')}
            </span>
          </div>

          {panel === 'history' && <NodeEventTimeline nodeId={node.id} />}
          {panel === 'stats' && <NodeStatsPanel nodeId={node.id} />}
        </div>

        {/* Actions */}
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
            title={panel === 'history' ? t('browsers.hideHistory') : t('browsers.eventHistory')}
          >
            {panel === 'history' ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {t('browsers.eventHistory')}
          </button>
          <button
            onClick={onDelete}
            disabled={isDeletePending}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
            title={t('browsers.deleteNode')}
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

// ── Bindings Section ──────────────────────────────────────────────────────────

interface BindingsSectionProps {
  nodes: EdgeNode[]
}

function BindingsSection({ nodes }: BindingsSectionProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [selectedEndpoint, setSelectedEndpoint] = useState('')
  const [selectedSite, setSelectedSite] = useState('')
  const [showAdd, setShowAdd] = useState(false)

  const { data: bindingsData } = useQuery({
    queryKey: ['browser-bindings'],
    queryFn: listBrowserBindings,
  })
  const bindings: BrowserBinding[] = bindingsData?.data ?? []
  const boundSites = new Set(bindings.map((b) => b.site))

  const addMut = useMutation({
    mutationFn: createBrowserBinding,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['browser-bindings'] })
      toast.success('站点绑定已添加')
      setShowAdd(false)
      setSelectedEndpoint('')
      setSelectedSite('')
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : '绑定失败'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteBrowserBinding,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['browser-bindings'] })
      toast.success('已解绑')
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : '解绑失败'),
  })

  const handleAdd = () => {
    if (!selectedEndpoint || !selectedSite) return
    addMut.mutate({ browser_endpoint: selectedEndpoint, site: selectedSite })
  }

  const nodeUrls = nodes.map((n) => n.url)

  // Group bindings by endpoint
  const byEndpoint: Record<string, BrowserBinding[]> = {}
  for (const b of bindings) {
    if (!byEndpoint[b.browser_endpoint]) byEndpoint[b.browser_endpoint] = []
    byEndpoint[b.browser_endpoint].push(b)
  }
  const orphaned = bindings.filter((b) => !nodeUrls.includes(b.browser_endpoint))

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-base font-semibold text-gray-800 dark:text-white">站点绑定</h2>
          <p className="text-xs text-gray-500 mt-0.5">将站点绑定到指定节点，触发时自动路由</p>
        </div>
        <button
          onClick={() => setShowAdd((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-blue-600 text-white hover:bg-blue-700"
        >
          <Plus size={14} />
          添加绑定
        </button>
      </div>

      {/* Add binding form */}
      {showAdd && (
        <Card>
          <div className="flex items-end gap-3 flex-wrap">
            <div className="flex-1 min-w-[160px]">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">节点端点</label>
              <select
                className={inputCls}
                value={selectedEndpoint}
                onChange={(e) => setSelectedEndpoint(e.target.value)}
              >
                <option value="">请选择节点…</option>
                {nodeUrls.map((url) => (
                  <option key={url} value={url}>{url}</option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-[160px]">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">站点</label>
              <div className="relative">
                <SiteDropdown
                  boundSites={boundSites}
                  onSelect={(site) => setSelectedSite(site)}
                  isPending={addMut.isPending}
                />
                {selectedSite && (
                  <span className="ml-2 text-xs text-blue-600 font-medium">
                    已选：{SITE_LABELS[selectedSite] ?? selectedSite}
                  </span>
                )}
              </div>
            </div>
            <div className="flex gap-2 pb-0.5">
              <button
                onClick={handleAdd}
                disabled={!selectedEndpoint || !selectedSite || addMut.isPending}
                className="px-3 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {t('common.create')}
              </button>
              <button
                onClick={() => { setShowAdd(false); setSelectedEndpoint(''); setSelectedSite('') }}
                className="px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                {t('common.cancel')}
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* Bindings list */}
      {bindings.length === 0 ? (
        <div className="text-center py-8 text-gray-400 text-sm border border-dashed border-gray-200 dark:border-gray-700 rounded-xl">
          {t('browsers.noBindings')}
        </div>
      ) : (
        <div className="space-y-3">
          {Object.entries(byEndpoint).map(([endpoint, eps]) => (
            <Card key={endpoint}>
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-mono text-gray-500 dark:text-gray-400 mb-2">{endpoint}</p>
                  <div className="flex flex-wrap gap-2">
                    {eps.map((b) => (
                      <span
                        key={b.id}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700"
                      >
                        {SITE_LABELS[b.site] ?? b.site}
                        <button
                          onClick={() => deleteMut.mutate(b.id)}
                          className="hover:text-red-500 transition-colors ml-0.5"
                        >
                          <X size={10} />
                        </button>
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          ))}

          {orphaned.length > 0 && (
            <div>
              <p className="text-xs text-gray-400 mb-2">{t('browsers.orphaned')}</p>
              <Card>
                <div className="flex flex-wrap gap-2">
                  {orphaned.map((b) => (
                    <span
                      key={b.id}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 border border-gray-200 dark:border-gray-600"
                    >
                      {SITE_LABELS[b.site] ?? b.site}
                      <span className="font-mono text-gray-400">→ {b.browser_endpoint}</span>
                      <button onClick={() => deleteMut.mutate(b.id)} className="hover:text-red-500 ml-0.5">
                        <X size={10} />
                      </button>
                    </span>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function NodesPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showWizard, setShowWizard] = useState(false)
  const [restartMsg, setRestartMsg] = useState<string | null>(null)

  // System config (collection mode)
  const { data: sysConfig } = useQuery({
    queryKey: ['system-config'],
    queryFn: getSystemConfig,
  })

  const switchModeMut = useMutation({
    mutationFn: (mode: 'local' | 'agent') => updateSystemConfig({ collection_mode: mode }),
    onSuccess: (newConfig) => {
      qc.setQueryData(['system-config'], newConfig)
      toast.success('采集模式已切换')
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : '切换失败'),
  })

  const restartMut = useMutation({
    mutationFn: restartApi,
    onSuccess: () => {
      setRestartMsg(t('browsers.restarting'))
      const poll = setInterval(() => {
        fetch('/api/v1/health')
          .then((r) => {
            if (r.ok) {
              clearInterval(poll)
              setRestartMsg(null)
            }
          })
          .catch(() => {})
      }, 2000)
      setTimeout(() => { clearInterval(poll); setRestartMsg(null) }, 30_000)
    },
  })

  // Nodes list (10s refresh)
  const { data: nodesData, isLoading: nodesLoading, error: nodesError, refetch } = useQuery({
    queryKey: ['nodes'],
    queryFn: listNodes,
    refetchInterval: 10_000,
  })
  const nodes: EdgeNode[] = nodesData?.data ?? []

  // WS agent status
  const { data: wsStatus } = useQuery({
    queryKey: ['ws-agent-status'],
    queryFn: getWsAgentStatus,
    refetchInterval: 10_000,
  })
  const wsConnectedSet = new Set(wsStatus?.connected ?? [])

  // Delete node
  const deleteNodeMut = useMutation({
    mutationFn: deleteNode,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nodes'] })
      toast.success('节点已删除')
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : '删除失败'),
  })

  if (nodesLoading) return <PageLoader />
  if (nodesError) return <ErrorAlert error={nodesError as Error} onRetry={refetch} />

  return (
    <div>
      <PageHeader title={t('browsers.title')} description={t('browsers.description')} />

      {/* ── Section 1: Collection mode + restart ── */}
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        {sysConfig && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800">
            <span className="text-xs text-gray-500 dark:text-gray-400 shrink-0">
              {t('browsers.collectionMode')}:
            </span>
            <div className="flex rounded-md overflow-hidden border border-gray-200 dark:border-gray-600 text-xs font-medium">
              {(['local', 'agent'] as const).map((mode) => (
                <button
                  key={mode}
                  disabled={switchModeMut.isPending}
                  onClick={() => sysConfig.collection_mode !== mode && switchModeMut.mutate(mode)}
                  className={[
                    'px-2.5 py-1 transition-colors',
                    sysConfig.collection_mode === mode
                      ? mode === 'local'
                        ? 'bg-blue-600 text-white'
                        : 'bg-purple-600 text-white'
                      : 'bg-white dark:bg-gray-800 text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700',
                  ].join(' ')}
                >
                  {mode === 'local' ? t('browsers.modeLocal') : t('browsers.modeAgent')}
                </button>
              ))}
            </div>
          </div>
        )}

        <button
          onClick={() => restartMut.mutate()}
          disabled={restartMut.isPending || !!restartMsg}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
        >
          <RefreshCw size={14} className={restartMsg ? 'animate-spin' : ''} />
          {restartMsg ?? t('browsers.restartApi')}
        </button>
      </div>

      {/* ── Section 2: EdgeNode list ── */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-base font-semibold text-gray-800 dark:text-white">边缘节点</h2>
          <p className="text-xs text-gray-500 mt-0.5">已注册的远端 Agent 节点</p>
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

      {/* ── Section 3: Bindings ── */}
      <BindingsSection nodes={nodes} />

      {/* Modals */}
      {showWizard && <InstallWizardModal onClose={() => setShowWizard(false)} />}
    </div>
  )
}
