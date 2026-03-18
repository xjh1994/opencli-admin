import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listSchedules, createSchedule, updateSchedule, deleteSchedule, listSources } from '../api/endpoints'
import type { CronSchedule } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import { Plus, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'
import { formatInTimeZone } from 'date-fns-tz'

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
  onClose,
  onSave,
}: {
  onClose: () => void
  onSave: (data: Partial<CronSchedule>) => void
}) {
  const { t } = useTranslation()
  const [sourceId, setSourceId] = useState('')
  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState('Asia/Shanghai')
  const [cronFields, setCronFields] = useState<CronFields>(DEFAULT_FIELDS)

  const { data: sourcesData } = useQuery({
    queryKey: ['sources', 'all'],
    queryFn: () => listSources({ page: 1, limit: 100 }),
  })
  const sources = sourcesData?.data ?? []

  const inputCls = 'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'
  const labelCls = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'

  const handleSave = () => {
    onSave({
      source_id: sourceId,
      name,
      cron_expression: buildCron(cronFields),
      timezone,
      is_one_time: cronFields.freq === 'once',
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-lg">
        <div className="p-6 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-lg font-semibold dark:text-white">{t('schedules.addScheduleTitle')}</h2>
        </div>

        <div className="p-6 space-y-4 overflow-y-auto max-h-[70vh]">
          {/* Source */}
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

          {/* Name */}
          <div>
            <label className={labelCls}>{t('common.name')}</label>
            <input
              className={inputCls}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="每天早上9点"
            />
          </div>

          {/* Cron builder */}
          <div>
            <label className={labelCls}>执行频率</label>
            <div className="border border-gray-200 dark:border-gray-600 rounded-lg p-3 bg-gray-50 dark:bg-gray-900/40">
              <CronBuilder fields={cronFields} onChange={setCronFields} />
            </div>
          </div>

          {/* Timezone */}
          <div>
            <label className={labelCls}>{t('schedules.timezone')}</label>
            <select className={inputCls} value={timezone} onChange={(e) => setTimezone(e.target.value)}>
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>{tz}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="p-6 border-t border-gray-100 dark:border-gray-700 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700">
            {t('common.cancel')}
          </button>
          <button
            onClick={handleSave}
            disabled={!sourceId}
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
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schedules'] }); setShowAdd(false) },
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => updateSchedule(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
  })

  const deleteMut = useMutation({
    mutationFn: deleteSchedule,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
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
        <AddScheduleModal onClose={() => setShowAdd(false)} onSave={(d) => createMut.mutate(d)} />
      )}
    </div>
  )
}
