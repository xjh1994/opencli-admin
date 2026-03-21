import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { listSchedules, createSchedule, updateSchedule, deleteSchedule, listSources, listAgents, getChromePool, listBrowserBindings, getSystemConfig, getWsAgentStatus } from '../api/endpoints'
import type { CronSchedule } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import { Plus, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'
import { SITE_LABELS } from '../components/ChannelConfigForm'
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

// ── Cron builder ───────────────────────────────────────────────────────────────

type FreqType = 'once' | 'minutely' | 'hourly' | 'daily' | 'weekly' | 'monthly' | 'custom'

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const FREQ_OPTIONS: { value: FreqType; label: string }[] = [
  { value: 'once',     label: '指定时间' },
  { value: 'minutely', label: '每 N 分钟' },
  { value: 'hourly',   label: '每小时' },
  { value: 'daily',    label: '每天' },
  { value: 'weekly',   label: '每周' },
  { value: 'monthly',  label: '每月' },
  { value: 'custom',   label: '自定义' },
]

const TIMEZONES = [
  'Asia/Shanghai',
  'Asia/Hong_Kong',
  'Asia/Taipei',
  'Asia/Tokyo',
  'Asia/Seoul',
  'Asia/Singapore',
  'Asia/Bangkok',
  'Asia/Kolkata',
  'Asia/Dubai',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Moscow',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'Australia/Sydney',
  'UTC',
]

interface CronFields {
  freq: FreqType
  datetime: string   // once: ISO local datetime string
  interval: number   // minutely: every N minutes
  minute: number     // 0-59
  hour: number       // 0-23
  weekday: number    // 0=Sun..6=Sat
  day: number        // 1-31
  custom: string
}

function buildCron(f: CronFields): string {
  switch (f.freq) {
    case 'once': {
      if (!f.datetime) return '0 0 1 1 *'
      const d = new Date(f.datetime)
      return `${d.getMinutes()} ${d.getHours()} ${d.getDate()} ${d.getMonth() + 1} *`
    }
    case 'minutely': return `*/${f.interval} * * * *`
    case 'hourly':   return `${f.minute} * * * *`
    case 'daily':    return `${f.minute} ${f.hour} * * *`
    case 'weekly':   return `${f.minute} ${f.hour} * * ${f.weekday}`
    case 'monthly':  return `${f.minute} ${f.hour} ${f.day} * *`
    case 'custom':   return f.custom
  }
}

const DEFAULT_FIELDS: CronFields = {
  freq: 'hourly', datetime: '', interval: 30, minute: 0, hour: 9, weekday: 1, day: 1, custom: '0 9 * * *',
}

function CronBuilder({ fields, onChange }: { fields: CronFields; onChange: (f: CronFields) => void }) {
  const set = (patch: Partial<CronFields>) => onChange({ ...fields, ...patch })

  const inputCls = 'border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1.5 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'
  const labelSm = 'text-xs text-gray-500 dark:text-gray-400 mr-1'

  return (
    <div className="space-y-3">
      {/* Frequency selector */}
      <div className="flex flex-wrap gap-1.5">
        {FREQ_OPTIONS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            onClick={() => set({ freq: value })}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              fields.freq === value
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Frequency-specific fields */}
      <div className="flex flex-wrap items-center gap-2 min-h-[36px]">
        {fields.freq === 'once' && (
          <div className="w-full space-y-1">
            <input
              type="datetime-local"
              className={`${inputCls} w-full cursor-pointer`}
              value={fields.datetime}
              onChange={(e) => set({ datetime: e.target.value })}
              onClick={(e) => (e.currentTarget as HTMLInputElement).showPicker?.()}
            />
            <p className="text-xs text-amber-600 dark:text-amber-400">执行完成后自动禁用</p>
          </div>
        )}
        {fields.freq === 'minutely' && (
          <>
            <span className={labelSm}>每</span>
            <select className={inputCls} value={fields.interval} onChange={(e) => set({ interval: +e.target.value })}>
              {[5, 10, 15, 20, 30].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            <span className={labelSm}>分钟执行一次</span>
          </>
        )}
        {fields.freq === 'hourly' && (
          <>
            <span className={labelSm}>每小时第</span>
            <select className={inputCls} value={fields.minute} onChange={(e) => set({ minute: +e.target.value })}>
              {Array.from({ length: 12 }, (_, i) => i * 5).map((m) => (
                <option key={m} value={m}>{String(m).padStart(2, '0')} 分</option>
              ))}
            </select>
            <span className={labelSm}>执行</span>
          </>
        )}
        {(fields.freq === 'daily' || fields.freq === 'weekly' || fields.freq === 'monthly') && (
          <>
            {fields.freq === 'weekly' && (
              <>
                <span className={labelSm}>每</span>
                <select className={inputCls} value={fields.weekday} onChange={(e) => set({ weekday: +e.target.value })}>
                  {WEEKDAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
                </select>
              </>
            )}
            {fields.freq === 'monthly' && (
              <>
                <span className={labelSm}>每月</span>
                <select className={inputCls} value={fields.day} onChange={(e) => set({ day: +e.target.value })}>
                  {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
                    <option key={d} value={d}>{d} 日</option>
                  ))}
                </select>
              </>
            )}
            <span className={labelSm}>{fields.freq === 'daily' ? '每天' : ''} </span>
            <select className={inputCls} value={fields.hour} onChange={(e) => set({ hour: +e.target.value })}>
              {Array.from({ length: 24 }, (_, i) => i).map((h) => (
                <option key={h} value={h}>{String(h).padStart(2, '0')} 时</option>
              ))}
            </select>
            <select className={inputCls} value={fields.minute} onChange={(e) => set({ minute: +e.target.value })}>
              {Array.from({ length: 12 }, (_, i) => i * 5).map((m) => (
                <option key={m} value={m}>{String(m).padStart(2, '0')} 分</option>
              ))}
            </select>
            <span className={labelSm}>执行</span>
          </>
        )}
        {fields.freq === 'custom' && (
          <input
            className={`${inputCls} w-full font-mono`}
            value={fields.custom}
            onChange={(e) => set({ custom: e.target.value })}
            placeholder="0 9 * * 1-5"
          />
        )}
      </div>

      {/* Cron preview */}
      <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span>Cron:</span>
        <code className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded font-mono text-gray-700 dark:text-gray-300">
          {buildCron(fields)}
        </code>
      </div>
    </div>
  )
}

// ── Modal ──────────────────────────────────────────────────────────────────────

function AddScheduleModal({
  isAgentMode,
  onClose,
  onSave,
}: {
  isAgentMode: boolean
  onClose: () => void
  onSave: (data: Partial<CronSchedule>) => void
}) {
  const { t } = useTranslation()
  const [sourceId, setSourceId] = useState('')
  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState('Asia/Shanghai')
  const [cronFields, setCronFields] = useState<CronFields>(DEFAULT_FIELDS)
  const [agentId, setAgentId] = useState('')
  const [chromeEndpoint, setChromeEndpoint] = useState('')

  const { data: sourcesData } = useQuery({
    queryKey: ['sources', 'all'],
    queryFn: () => listSources({ page: 1, limit: 100 }),
  })
  const sources = sourcesData?.data ?? []

  const { data: agentsData } = useQuery({
    queryKey: ['agents', 'enabled'],
    queryFn: () => listAgents({ enabled: true }),
  })
  const agents = agentsData?.data ?? []

  const { data: chromePool } = useQuery({
    queryKey: ['chrome-pool'],
    queryFn: getChromePool,
  })
  const chromeEndpoints = chromePool?.endpoints ?? []
  const selectedSource = sources.find((s) => s.id === sourceId)

  const agentEndpoints = isAgentMode ? chromeEndpoints.filter((ep) => ep.agent_url != null && ep.agent_url !== '') : []
  const showAgentSelector = selectedSource?.channel_type === 'opencli' && isAgentMode && agentEndpoints.length > 0
  const showChromeSelector = selectedSource?.channel_type === 'opencli' && !isAgentMode && chromeEndpoints.length >= 1

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
  })
  const bindings = bindingsData?.data ?? []

  // endpoint → bound site names map (for display)
  const endpointBoundSites: Record<string, string[]> = {}
  for (const b of bindings) {
    if (!endpointBoundSites[b.browser_endpoint]) endpointBoundSites[b.browser_endpoint] = []
    endpointBoundSites[b.browser_endpoint].push(b.site)
  }

  // Auto-select Chrome: prefer endpoint bound to source's site, else single-endpoint fallback
  useEffect(() => {
    if (isAgentMode) return
    const site = selectedSource?.channel_config?.site as string | undefined
    if (site) {
      const binding = bindings.find((b) => b.site === site)
      if (binding) { setChromeEndpoint(binding.browser_endpoint); return }
    }
    if (chromeEndpoints.length === 1) {
      setChromeEndpoint(chromeEndpoints[0].url)
    } else {
      setChromeEndpoint('')
    }
  }, [chromeEndpoints, bindingsData, sourceId])

  const inputCls = 'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'
  const labelCls = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'

  const handleSave = () => {
    onSave({
      source_id: sourceId,
      name,
      cron_expression: buildCron(cronFields),
      timezone,
      is_one_time: cronFields.freq === 'once',
      agent_id: agentId || undefined,
      parameters: chromeEndpoint ? { chrome_endpoint: chromeEndpoint } : {},
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-2xl">
        <div className="p-6 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-lg font-semibold dark:text-white">{t('schedules.addScheduleTitle')}</h2>
        </div>

        <div className="p-6 space-y-4 overflow-y-auto max-h-[75vh]">
          {/* Source + Name */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>
                数据源 <span className="text-red-500">*</span>
              </label>
              <select className={inputCls} value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
                <option value="">— 选择数据源 —</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}（{formatInTimeZone(new Date(s.created_at), 'Asia/Shanghai', 'MM-dd HH:mm')}）
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelCls}>{t('common.name')} <span className="text-red-500">*</span></label>
              <input
                className={inputCls}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="每天早上9点"
              />
            </div>
          </div>

          {/* Cron builder */}
          <div>
            <label className={labelCls}>执行频率</label>
            <div className="border border-gray-200 dark:border-gray-600 rounded-lg p-3 bg-gray-50 dark:bg-gray-900/40">
              <CronBuilder fields={cronFields} onChange={setCronFields} />
            </div>
          </div>

          {/* Timezone + Agent */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>{t('schedules.timezone')}</label>
              <select className={inputCls} value={timezone} onChange={(e) => setTimezone(e.target.value)}>
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelCls}>{t('agents.selectAgent')}</label>
              <select className={inputCls} value={agentId} onChange={(e) => setAgentId(e.target.value)}>
                <option value="">{t('agents.noAgent')}</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    [{a.processor_type}] {a.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {showAgentSelector && (
            <div>
              <div className="flex items-center gap-2 mb-1">
                <label className={labelCls} style={{ marginBottom: 0 }}>采集节点</label>
                <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300">Agent 模式</span>
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer py-1">
                  <input
                    type="radio"
                    name="agent-ep-sched"
                    value=""
                    checked={chromeEndpoint === ''}
                    onChange={() => setChromeEndpoint('')}
                    className="accent-blue-600 shrink-0"
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-300">自动分配</span>
                </label>
                {agentEndpoints.map((ep) => {
                  const isWs = ep.agent_protocol === 'ws'
                  const isConnected = isWs ? wsConnectedSet.has(ep.agent_url ?? '') : ep.available
                  const label = (ep.agent_url ?? ep.url).replace(/^https?:\/\//, '')
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
                        name="agent-ep-sched"
                        value={ep.url}
                        checked={chromeEndpoint === ep.url}
                        onChange={() => setChromeEndpoint(ep.url)}
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
              <p className="mt-1 text-xs text-gray-400">{t('channelConfig.chromeEndpointHint')}</p>
            </div>
          )}

          {showChromeSelector && (
            <div>
              <div className="flex items-center gap-2 mb-1">
                <label className={labelCls} style={{ marginBottom: 0 }}>{t('channelConfig.chromeEndpoint')}</label>
                <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">本地模式</span>
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer py-1">
                  <input
                    type="radio"
                    name="chrome-ep-sched"
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
                        name="chrome-ep-sched"
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
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700">
            {t('common.cancel')}
          </button>
          <button
            onClick={handleSave}
            disabled={!sourceId || !name.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {t('common.create')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function SchedulesPage() {
  const { t } = useTranslation()
  const [showAdd, setShowAdd] = useState(false)
  const qc = useQueryClient()

  const { data: sysConfig } = useQuery({
    queryKey: ['system-config'],
    queryFn: getSystemConfig,
  })
  const isAgentMode = sysConfig?.collection_mode === 'agent'

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['schedules'],
    queryFn: () => listSchedules(),
  })

  const { data: sourcesData } = useQuery({
    queryKey: ['sources', 'all'],
    queryFn: () => listSources({ page: 1, limit: 100 }),
  })
  const sourceNameMap = Object.fromEntries((sourcesData?.data ?? []).map((s) => [s.id, s.name]))

  const createMut = useMutation({
    mutationFn: createSchedule,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schedules'] }); setShowAdd(false); toast.success('计划已保存') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '操作失败'),
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => updateSchedule(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
  })

  const deleteMut = useMutation({
    mutationFn: deleteSchedule,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schedules'] }); toast.success('已删除') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '删除失败'),
  })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorAlert error={error as Error} onRetry={refetch} />

  const schedules: CronSchedule[] = data?.data ?? []

  return (
    <div>
      <PageHeader
        title={t('schedules.title')}
        description={t('schedules.description')}
        action={
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            <Plus size={16} /> {t('schedules.addSchedule')}
          </button>
        }
      />

      <Card padding={false}>
        <DataTable
          data={schedules}
          keyFn={(s) => s.id}
          emptyMessage={t('schedules.noSchedules')}
          columns={[
            { key: 'name', header: t('common.name'), width: '150px', render: (s) => <span className="font-medium">{s.name}</span> },
            {
              key: 'source',
              header: '数据源',
              width: '150px',
              render: (s) => (
                <div>
                  {sourceNameMap[s.source_id] && <p className="text-sm font-medium">{sourceNameMap[s.source_id]}</p>}
                  <p className="font-mono text-xs text-gray-400">{s.source_id.slice(0, 8)}…</p>
                </div>
              ),
            },
            {
              key: 'cron',
              header: t('schedules.cronExpression'),
              width: '130px',
              render: (s) => (
                <code className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs font-mono">
                  {s.cron_expression}
                </code>
              ),
            },
            { key: 'tz', header: t('schedules.timezone'), width: '130px', render: (s) => <span className="text-xs">{s.timezone}</span> },
            {
              key: 'last_run',
              header: t('schedules.lastRun'),
              width: '110px',
              render: (s) => (
                <span className="text-xs text-gray-500">
                  {s.last_run_at
                    ? formatInTimeZone(new Date(s.last_run_at), 'Asia/Shanghai', 'MM-dd HH:mm')
                    : '—'}
                </span>
              ),
            },
            {
              key: 'status',
              header: t('schedules.enabledCol'),
              width: '70px',
              render: (s) => (
                <span className={`text-xs font-medium ${s.enabled ? 'text-green-600' : 'text-gray-400'}`}>
                  {s.enabled ? t('common.yes') : t('common.no')}
                </span>
              ),
            },
            {
              key: 'actions',
              header: t('common.actions'),
              width: '100px',
              render: (s) => (
                <div className="flex gap-1">
                  <button onClick={() => toggleMut.mutate({ id: s.id, enabled: !s.enabled })}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500">
                    {s.enabled ? <ToggleRight size={12} /> : <ToggleLeft size={12} />}
                    {s.enabled ? t('common.disable') : t('common.enable')}
                  </button>
                  <button
                    onClick={() => { if (confirm(t('schedules.confirmDelete', { name: s.name }))) deleteMut.mutate(s.id) }}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500">
                    <Trash2 size={12} /> 删除
                  </button>
                </div>
              ),
            },
          ]}
        />
      </Card>

      {showAdd && (
        <AddScheduleModal isAgentMode={isAgentMode} onClose={() => setShowAdd(false)} onSave={(d) => createMut.mutate(d)} />
      )}
    </div>
  )
}
