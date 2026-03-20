import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { listSources, createSource, updateSource, deleteSource, triggerTask, listAgents, getChromePool, listBrowserBindings, getSystemConfig, getWsAgentStatus } from '../api/endpoints'
import type { DataSource } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import ChannelConfigForm, { type ChannelType, PRESET_DEFAULT, SITE_LABELS, COMMANDS_BY_SITE } from '../components/ChannelConfigForm'
import { Plus, Play, Trash2, ToggleLeft, ToggleRight, Pencil } from 'lucide-react'
import { formatInTimeZone } from 'date-fns-tz'

/** Derive noVNC port from CDP URL using chrome-N hostname convention. */
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

const CHANNEL_COLORS: Record<string, string> = {
  opencli:     'bg-indigo-100 text-indigo-700',
  web_scraper: 'bg-orange-100 text-orange-700',
  api:         'bg-teal-100 text-teal-700',
  rss:         'bg-pink-100 text-pink-700',
  cli:         'bg-yellow-100 text-yellow-700',
}

function ChannelBadge({ type }: { type: string }) {
  const cls = CHANNEL_COLORS[type] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {type}
    </span>
  )
}

const CHANNEL_TYPES: ChannelType[] = ['opencli', 'rss', 'api', 'web_scraper', 'cli']

const inputCls =
  'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'
const labelCls = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'

function genDefaultName(type: ChannelType, config: Record<string, unknown>): string {
  const now = new Date()
  const ts = `${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`
  if (type === 'opencli') {
    const site = (config.site as string) || ''
    const cmd  = (config.command as string) || ''
    const siteLabel = SITE_LABELS[site] || site
    const preset = COMMANDS_BY_SITE[site]?.find((p) => p.command === cmd)
    const cmdLabel = preset ? preset.label.split(' · ').slice(1).join(' · ') : cmd
    return [siteLabel, cmdLabel, ts].filter(Boolean).join('-')
  }
  return `${type}-${ts}`
}

function SourceModal({
  initial,
  onClose,
  onSave,
}: {
  initial?: DataSource
  onClose: () => void
  onSave: (data: Partial<DataSource>) => void
}) {
  const { t } = useTranslation()
  const isEdit = !!initial

  const initConfig: Record<string, unknown> = isEdit
    ? (initial.channel_config as Record<string, unknown>) ?? {}
    : { site: PRESET_DEFAULT.site, command: PRESET_DEFAULT.command, args: PRESET_DEFAULT.args, format: 'json' }

  const initType: ChannelType = isEdit ? (initial.channel_type as ChannelType) : 'opencli'

  const [channelType, setChannelType] = useState<ChannelType>(initType)
  const [channelConfig, setChannelConfig] = useState<Record<string, unknown>>(initConfig)
  const [configCache, setConfigCache] = useState<Partial<Record<ChannelType, Record<string, unknown>>>>({
    [initType]: initConfig,
  })
  const [name, setName] = useState(isEdit ? initial.name : () => genDefaultName('opencli', initConfig))
  const [nameEdited, setNameEdited] = useState(isEdit)
  const [description, setDescription] = useState(isEdit ? (initial.description ?? '') : '')

  const handleConfigChange = (cfg: Record<string, unknown>) => {
    setChannelConfig(cfg)
    setConfigCache((prev) => ({ ...prev, [channelType]: cfg }))
    if (!nameEdited) setName(genDefaultName(channelType, cfg))
  }

  const handleTypeChange = (type: ChannelType) => {
    setConfigCache((prev) => ({ ...prev, [channelType]: channelConfig }))
    const restored = configCache[type] ?? (type === 'opencli' ? initConfig : {})
    setChannelType(type)
    setChannelConfig(restored)
    if (!nameEdited) setName(genDefaultName(type, restored))
  }

  const handleSubmit = () => {
    onSave({ name, description, channel_type: channelType, channel_config: channelConfig, enabled: true, tags: [] })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="p-6 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-lg font-semibold dark:text-white">
            {isEdit ? t('sources.editSourceTitle') : t('sources.addSourceTitle')}
          </h2>
        </div>

        <div className="p-6 overflow-y-auto flex-1 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>
                {t('common.name')} <span className="text-red-500">*</span>
              </label>
              <input
                className={inputCls}
                value={name}
                onChange={(e) => { setName(e.target.value); setNameEdited(true) }}
                placeholder="my-source"
              />
            </div>
            <div>
              <label className={labelCls}>{t('sources.channelType')}</label>
              <select
                className={inputCls}
                value={channelType}
                onChange={(e) => handleTypeChange(e.target.value as ChannelType)}
                disabled={isEdit}
              >
                {CHANNEL_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}{type !== 'opencli' ? '（开发中）' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className={labelCls}>{t('common.description')}</label>
            <input
              className={inputCls}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div>
            <p className={labelCls}>{t('sources.channelConfig')}</p>
            <div className="border border-gray-200 dark:border-gray-600 rounded-lg p-4 bg-gray-50 dark:bg-gray-900/40">
              <ChannelConfigForm
                channelType={channelType}
                config={channelConfig}
                onChange={handleConfigChange}
              />
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-gray-100 dark:border-gray-700 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={handleSubmit}
            disabled={!name.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {isEdit ? t('common.save') : t('common.create')}
          </button>
        </div>
      </div>
    </div>
  )
}

function TriggerModal({
  source,
  isAgentMode,
  onClose,
  onTrigger,
}: {
  source: DataSource
  isAgentMode: boolean
  onClose: () => void
  onTrigger: (agentId?: string, parameters?: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  const [agentId, setAgentId] = useState('')
  const [chromeEndpoint, setChromeEndpoint] = useState('')
  const [selectedAgentEndpoints, setSelectedAgentEndpoints] = useState<Set<string>>(new Set())

  const { data: agentsData } = useQuery({
    queryKey: ['agents', 'enabled'],
    queryFn: () => listAgents({ enabled: true }),
  })
  const agents = agentsData?.data ?? []

  const { data: chromePool } = useQuery({
    queryKey: ['chrome-pool'],
    queryFn: getChromePool,
    enabled: source.channel_type === 'opencli',
  })
  const chromeEndpoints = chromePool?.endpoints ?? []

  // agent mode: show endpoints with agent_url configured
  const agentEndpoints = isAgentMode ? chromeEndpoints.filter((ep) => ep.agent_url != null && ep.agent_url !== '') : []
  const showAgentSelector = isAgentMode && agentEndpoints.length > 0

  // local mode: show Chrome instance selector
  const showChromeSelector = source.channel_type === 'opencli' && !isAgentMode && chromeEndpoints.length >= 1

  const { data: wsStatus } = useQuery({
    queryKey: ['ws-agent-status'],
    queryFn: getWsAgentStatus,
    enabled: isAgentMode,
    refetchInterval: 10_000,
  })
  const wsConnectedSet = new Set(wsStatus?.connected ?? [])

  const { data: bindingsData } = useQuery({
    queryKey: ['browser-bindings'],
    queryFn: listBrowserBindings,
    enabled: source.channel_type === 'opencli',
  })
  const bindings = bindingsData?.data ?? []

  const endpointBoundSites: Record<string, string[]> = {}
  for (const b of bindings) {
    if (!endpointBoundSites[b.browser_endpoint]) endpointBoundSites[b.browser_endpoint] = []
    endpointBoundSites[b.browser_endpoint].push(b.site)
  }

  // Auto-select Chrome endpoint from binding or single-endpoint fallback
  useEffect(() => {
    if (isAgentMode) return
    const site = source.channel_config?.site as string | undefined
    if (site) {
      const binding = bindings.find((b) => b.site === site)
      if (binding) { setChromeEndpoint(binding.browser_endpoint); return }
    }
    if (chromeEndpoints.length === 1 && !chromeEndpoint) {
      setChromeEndpoint(chromeEndpoints[0].url)
    }
  }, [chromeEndpoints, bindingsData])

  const toggleAgentEndpoint = (url: string) => {
    setSelectedAgentEndpoints((prev) => {
      const next = new Set(prev)
      if (next.has(url)) next.delete(url)
      else next.add(url)
      return next
    })
  }

  const handleTrigger = () => {
    if (isAgentMode) {
      const endpoints = [...selectedAgentEndpoints]
      if (endpoints.length === 0) {
        // auto: let the pool pick any agent
        onTrigger(agentId || undefined, undefined)
      } else if (endpoints.length === 1) {
        onTrigger(agentId || undefined, { chrome_endpoint: endpoints[0] })
      } else {
        // multi: fire one task per selected agent, close immediately
        endpoints.forEach((ep) => onTrigger(agentId || undefined, { chrome_endpoint: ep }))
        onClose()
      }
    } else {
      const params: Record<string, unknown> = {}
      if (chromeEndpoint) params.chrome_endpoint = chromeEndpoint
      onTrigger(agentId || undefined, Object.keys(params).length ? params : undefined)
    }
  }

  const triggerLabel = isAgentMode && selectedAgentEndpoints.size > 1
    ? `触发 ${selectedAgentEndpoints.size} 个节点`
    : t('sources.triggerNow')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-lg">
        <div className="p-6 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-lg font-semibold dark:text-white">{t('agents.triggerTitle')}</h2>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className={labelCls}>{t('agents.selectAgent')}</label>
            <select className={inputCls} value={agentId} onChange={(e) => setAgentId(e.target.value)}>
              <option value="">{t('agents.noAgent')}</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>[{a.processor_type}] {a.name}</option>
              ))}
            </select>
          </div>

          {showAgentSelector && (
            <div>
              <label className={labelCls}>采集节点</label>
              <div className="space-y-2">
                {agentEndpoints.map((ep) => {
                  const isWs = ep.agent_protocol === 'ws'
                  const isConnected = isWs ? wsConnectedSet.has(ep.agent_url ?? '') : ep.available
                  const label = (ep.agent_url ?? ep.url).replace(/^https?:\/\//, '')
                  return (
                    <label
                      key={ep.url}
                      className={`flex gap-3 cursor-pointer rounded-lg border px-3 py-2.5 transition-colors ${
                        selectedAgentEndpoints.has(ep.url)
                          ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-500'
                          : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedAgentEndpoints.has(ep.url)}
                        onChange={() => toggleAgentEndpoint(ep.url)}
                        className="accent-blue-600 shrink-0 mt-0.5"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`text-sm font-medium font-mono ${isConnected ? 'text-gray-800 dark:text-gray-200' : 'text-gray-400'}`}>
                            {label}
                          </span>
                          <span className={`text-xs ${isConnected ? 'text-green-500' : 'text-red-400'}`}>
                            {isConnected ? '● 在线' : '○ 离线'}
                          </span>
                          <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                            isWs
                              ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300'
                              : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                          }`}>
                            {isWs ? 'WS' : 'HTTP'}
                          </span>
                        </div>
                      </div>
                    </label>
                  )
                })}
              </div>
              <p className="mt-1 text-xs text-gray-400">
                {selectedAgentEndpoints.size === 0
                  ? '未选择则自动分配'
                  : `已选 ${selectedAgentEndpoints.size} 个节点，将触发 ${selectedAgentEndpoints.size} 个任务`}
              </p>
            </div>
          )}

          {showChromeSelector && (
            <div>
              <label className={labelCls}>{t('channelConfig.chromeEndpoint')}</label>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer py-1">
                  <input
                    type="radio"
                    name="chrome-ep"
                    value=""
                    checked={chromeEndpoint === ''}
                    onChange={() => setChromeEndpoint('')}
                    className="accent-blue-600 shrink-0"
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-300">{t('channelConfig.chromeEndpointAny')}</span>
                </label>
                {chromeEndpoints.map((ep) => {
                  const novncPort = ep.novnc_port ?? chromeNovncPort(ep.url)
                  const novncUrl = `http://${window.location.hostname}:${novncPort}`
                  const label = ep.url.replace('http://', '').replace(':19222', '')
                  const boundSites = endpointBoundSites[ep.url] ?? []
                  return (
                    <label
                      key={ep.url}
                      className={`flex gap-3 cursor-pointer rounded-lg border px-3 py-2.5 transition-colors ${
                        chromeEndpoint === ep.url
                          ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-500'
                          : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                      }`}
                    >
                      <input
                        type="radio"
                        name="chrome-ep"
                        value={ep.url}
                        checked={chromeEndpoint === ep.url}
                        onChange={() => setChromeEndpoint(ep.url)}
                        className="accent-blue-600 shrink-0 mt-0.5"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`text-sm font-medium ${ep.available ? 'text-gray-800 dark:text-gray-200' : 'text-gray-400'}`}>
                            {label}
                          </span>
                          <span className={`text-xs ${ep.available ? 'text-green-500' : 'text-red-400'}`}>
                            {ep.available ? '● 在线' : '○ 离线'}
                          </span>
                          <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${ep.mode === 'bridge' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'}`}>
                            {ep.mode === 'bridge' ? 'Bridge' : 'CDP'}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                          {boundSites.map((site) => (
                            <span key={site} className="px-1.5 py-0.5 rounded text-xs bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
                              {SITE_LABELS[site] ?? site}
                            </span>
                          ))}
                          {boundSites.length === 0 && (
                            <span className="text-xs text-gray-400">暂无绑定站点</span>
                          )}
                          <a
                            href={novncUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="ml-auto text-xs text-blue-500 hover:underline font-mono shrink-0"
                          >
                            noVNC ↗
                          </a>
                        </div>
                      </div>
                    </label>
                  )
                })}
              </div>
              <p className="mt-1 text-xs text-gray-400">{t('channelConfig.chromeEndpointHint')}</p>
            </div>
          )}
        </div>
        <div className="p-6 border-t border-gray-100 dark:border-gray-700 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={handleTrigger}
            className="px-4 py-2 text-sm rounded-lg bg-green-600 text-white hover:bg-green-700"
          >
            {triggerLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function SourcesPage() {
  const { t } = useTranslation()
  const [showAdd, setShowAdd] = useState(false)
  const [editSource, setEditSource] = useState<DataSource | null>(null)
  const [triggerSource, setTriggerSource] = useState<DataSource | null>(null)
  const [page, setPage] = useState(1)
  const qc = useQueryClient()

  const { data: sysConfig } = useQuery({
    queryKey: ['system-config'],
    queryFn: getSystemConfig,
  })
  const isAgentMode = sysConfig?.collection_mode === 'agent'

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['sources', page],
    queryFn: () => listSources({ page, limit: 20 }),
  })

  const createMut = useMutation({
    mutationFn: createSource,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sources'] }); setShowAdd(false); toast.success('数据源已创建') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '创建失败'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<DataSource> }) => updateSource(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sources'] }); setEditSource(null); toast.success('数据源已更新') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '更新失败'),
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => updateSource(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  const deleteMut = useMutation({
    mutationFn: deleteSource,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sources'] }); toast.success('已删除') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '删除失败'),
  })

  const [triggerStates, setTriggerStates] = useState<Record<string, 'loading' | 'ok' | 'err'>>({})

  const triggerMut = useMutation({
    mutationFn: ({ id, agentId, parameters }: { id: string; agentId?: string; parameters?: Record<string, unknown> }) =>
      triggerTask(id, parameters ?? {}, agentId),
    onMutate: ({ id }) => setTriggerStates((s) => ({ ...s, [id]: 'loading' })),
    onSuccess: (_data, { id }) => {
      setTriggerStates((s) => ({ ...s, [id]: 'ok' }))
      setTimeout(() => setTriggerStates((s) => { const n = { ...s }; delete n[id]; return n }), 2000)
      setTriggerSource(null)
      toast.success('任务已触发')
    },
    onError: (_err, { id }) => {
      setTriggerStates((s) => ({ ...s, [id]: 'err' }))
      setTimeout(() => setTriggerStates((s) => { const n = { ...s }; delete n[id]; return n }), 3000)
      setTriggerSource(null)
      toast.error(_err instanceof Error ? _err.message : '触发失败')
    },
  })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorAlert error={error as Error} onRetry={refetch} />

  const sources = data?.data ?? []
  const meta = data?.meta

  return (
    <div>
      <PageHeader
        title={t('sources.title')}
        description={t('sources.description')}
        action={
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={16} /> {t('sources.addSource')}
          </button>
        }
      />

      <Card padding={false}>
        <DataTable
          data={sources}
          keyFn={(s) => s.id}
          emptyMessage={t('sources.noSources')}
          columns={[
            {
              key: 'name',
              header: t('common.name'),
              width: '220px',
              render: (s) => (
                <div>
                  <p className="font-medium">{s.name}</p>
                  {s.description && <p className="text-xs text-gray-400">{s.description}</p>}
                </div>
              ),
            },
            {
              key: 'type',
              header: t('sources.channelType'),
              render: (s) => <ChannelBadge type={s.channel_type} />,
              width: '100px',
            },
            {
              key: 'status',
              header: t('common.status'),
              render: (s) => <StatusBadge status={s.enabled ? 'online' : 'offline'} />,
              width: '80px',
            },
            {
              key: 'created_at',
              header: t('common.createdAt'),
              width: '120px',
              render: (s) => (
                <span className="text-xs text-gray-500">
                  {formatInTimeZone(new Date(s.created_at), 'Asia/Shanghai', 'MM-dd HH:mm')}
                </span>
              ),
            },
            {
              key: 'updated_at',
              header: t('common.updatedAt'),
              width: '120px',
              render: (s) => (
                <span className="text-xs text-gray-500">
                  {formatInTimeZone(new Date(s.updated_at), 'Asia/Shanghai', 'MM-dd HH:mm')}
                </span>
              ),
            },
            {
              key: 'actions',
              header: t('common.actions'),
              width: '210px',
              render: (s) => (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setTriggerSource(s)}
                    disabled={!!triggerStates[s.id]}
                    className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors disabled:cursor-default ${
                      triggerStates[s.id] === 'ok'  ? 'text-green-600 bg-green-50 dark:bg-green-900/30' :
                      triggerStates[s.id] === 'err' ? 'text-red-500 bg-red-50 dark:bg-red-900/30' :
                      'hover:bg-green-100 dark:hover:bg-green-900/30 text-green-600'
                    }`}
                  >
                    {triggerStates[s.id] === 'loading' ? <><span className="animate-spin inline-block w-3 h-3 border border-current border-t-transparent rounded-full" /> 触发中</> :
                     triggerStates[s.id] === 'ok'      ? <>✓ 已触发</> :
                     triggerStates[s.id] === 'err'     ? <>✗ 失败</> :
                     <><Play size={12} /> 触发</>}
                  </button>
                  <button
                    onClick={() => toggleMut.mutate({ id: s.id, enabled: !s.enabled })}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500"
                  >
                    {s.enabled ? <ToggleRight size={12} /> : <ToggleLeft size={12} />}
                    {s.enabled ? t('common.disable') : t('common.enable')}
                  </button>
                  <button
                    onClick={() => setEditSource(s)}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-blue-100 dark:hover:bg-blue-900/30 text-blue-600"
                  >
                    <Pencil size={12} /> 编辑
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(t('sources.confirmDelete', { name: s.name }))) deleteMut.mutate(s.id)
                    }}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500"
                  >
                    <Trash2 size={12} /> 删除
                  </button>
                </div>
              ),
            },
          ]}
        />

        {meta && meta.pages > 1 && (
          <div className="px-5 py-3 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between text-sm">
            <span className="text-gray-500">{t('sources.totalSources', { count: meta.total })}</span>
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

      {showAdd && (
        <SourceModal
          onClose={() => setShowAdd(false)}
          onSave={(d) => createMut.mutate(d)}
        />
      )}

      {editSource && (
        <SourceModal
          initial={editSource}
          onClose={() => setEditSource(null)}
          onSave={(d) => updateMut.mutate({ id: editSource.id, data: d })}
        />
      )}

      {triggerSource && (
        <TriggerModal
          source={triggerSource}
          isAgentMode={isAgentMode}
          onClose={() => setTriggerSource(null)}
          onTrigger={(agentId, parameters) =>
            triggerMut.mutate({ id: triggerSource.id, agentId, parameters })
          }
        />
      )}
    </div>
  )
}
