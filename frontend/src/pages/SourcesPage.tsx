import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listSources, createSource, updateSource, deleteSource, triggerTask } from '../api/endpoints'
import type { DataSource } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import StatusBadge from '../components/StatusBadge'
import PageHeader from '../components/PageHeader'
import ChannelConfigForm, { type ChannelType, PRESET_DEFAULT } from '../components/ChannelConfigForm'
import { Plus, Play, Trash2, ToggleLeft, ToggleRight, Tag } from 'lucide-react'
import { formatInTimeZone } from 'date-fns-tz'

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
    return [site, cmd, ts].filter(Boolean).join('-')
  }
  return `${type}-${ts}`
}

function AddSourceModal({
  onClose,
  onSave,
}: {
  onClose: () => void
  onSave: (data: Partial<DataSource>) => void
}) {
  const { t } = useTranslation()
  const initConfig: Record<string, unknown> = {
    site: PRESET_DEFAULT.site,
    command: PRESET_DEFAULT.command,
    args: PRESET_DEFAULT.args,
    format: 'json',
  }
  const [channelType, setChannelType] = useState<ChannelType>('opencli')
  const [channelConfig, setChannelConfig] = useState<Record<string, unknown>>(initConfig)
  const [name, setName] = useState(() => genDefaultName('opencli', initConfig))
  const [nameEdited, setNameEdited] = useState(false)
  const [description, setDescription] = useState('')

  const handleConfigChange = (cfg: Record<string, unknown>) => {
    setChannelConfig(cfg)
    if (!nameEdited) setName(genDefaultName(channelType, cfg))
  }

  const handleTypeChange = (type: ChannelType) => {
    setChannelType(type)
    if (!nameEdited) setName(genDefaultName(type, {}))
  }

  const handleSubmit = () => {
    onSave({ name, description, channel_type: channelType, channel_config: channelConfig, enabled: true, tags: [] })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="p-6 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-lg font-semibold dark:text-white">{t('sources.addSourceTitle')}</h2>
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
              >
                {CHANNEL_TYPES.map((type) => (
                  <option key={type} value={type}>{type}</option>
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
            {t('common.create')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function SourcesPage() {
  const { t } = useTranslation()
  const [showAdd, setShowAdd] = useState(false)
  const [page, setPage] = useState(1)
  const qc = useQueryClient()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['sources', page],
    queryFn: () => listSources({ page, limit: 20 }),
  })

  const createMut = useMutation({
    mutationFn: createSource,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sources'] }); setShowAdd(false) },
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => updateSource(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  const deleteMut = useMutation({
    mutationFn: deleteSource,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  const triggerMut = useMutation({ mutationFn: (id: string) => triggerTask(id) })

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
              width: '130px',
            },
            {
              key: 'tags',
              header: 'Tags',
              render: (s) => (
                <div className="flex flex-wrap gap-1">
                  {s.tags.map((tag) => (
                    <span key={tag} className="flex items-center gap-0.5 px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs">
                      <Tag size={10} /> {tag}
                    </span>
                  ))}
                </div>
              ),
            },
            {
              key: 'status',
              header: t('common.status'),
              render: (s) => <StatusBadge status={s.enabled ? 'online' : 'offline'} />,
              width: '90px',
            },
            {
              key: 'id',
              header: t('common.id'),
              width: '100px',
              render: (s) => (
                <span className="font-mono text-xs text-gray-400">{s.id.slice(0, 8)}</span>
              ),
            },
            {
              key: 'created_at',
              header: t('common.createdAt'),
              width: '130px',
              render: (s) => (
                <span className="text-xs text-gray-500">
                  {formatInTimeZone(new Date(s.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                </span>
              ),
            },
            {
              key: 'updated_at',
              header: t('common.updatedAt'),
              width: '130px',
              render: (s) => (
                <span className="text-xs text-gray-500">
                  {formatInTimeZone(new Date(s.updated_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}
                </span>
              ),
            },
            {
              key: 'actions',
              header: t('common.actions'),
              width: '130px',
              render: (s) => (
                <div className="flex items-center gap-2">
                  <button
                    title={t('sources.triggerNow')}
                    onClick={() => triggerMut.mutate(s.id)}
                    className="p-1.5 rounded hover:bg-green-100 dark:hover:bg-green-900/30 text-green-600"
                  >
                    <Play size={14} />
                  </button>
                  <button
                    title={s.enabled ? t('common.disable') : t('common.enable')}
                    onClick={() => toggleMut.mutate({ id: s.id, enabled: !s.enabled })}
                    className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500"
                  >
                    {s.enabled ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                  </button>
                  <button
                    title={t('common.delete')}
                    onClick={() => {
                      if (confirm(t('sources.confirmDelete', { name: s.name }))) deleteMut.mutate(s.id)
                    }}
                    className="p-1.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500"
                  >
                    <Trash2 size={14} />
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
        <AddSourceModal
          onClose={() => setShowAdd(false)}
          onSave={(d) => createMut.mutate(d)}
        />
      )}
    </div>
  )
}
