import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { listProviders, createProvider, updateProvider, deleteProvider } from '../api/endpoints'
import type { ModelProvider } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import { Plus, Pencil, Trash2, ToggleLeft, ToggleRight, Eye, EyeOff } from 'lucide-react'

const inputCls =
  'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'
const labelCls = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'

const PROVIDER_TYPE_OPTIONS = [
  { value: 'claude', label: 'Claude (Anthropic)' },
  { value: 'openai', label: 'OpenAI 兼容' },
  { value: 'local',  label: '本地模型（Ollama 等）' },
]

const PROVIDER_PRESETS: Record<string, { base_url: string; label: string }> = {
  openai:    { base_url: 'https://api.openai.com/v1',                   label: 'OpenAI 官方' },
  deepseek:  { base_url: 'https://api.deepseek.com/v1',                 label: 'DeepSeek' },
  kimi:      { base_url: 'https://api.moonshot.cn/v1',                  label: 'Kimi (Moonshot)' },
  glm:       { base_url: 'https://open.bigmodel.cn/api/paas/v4/',       label: 'GLM (智谱)' },
  minimax:   { base_url: 'https://api.minimax.chat/v1',                 label: 'MiniMax' },
  ollama:    { base_url: 'http://localhost:11434',                       label: 'Ollama 本地' },
}

const PROCESSOR_COLORS: Record<string, string> = {
  claude: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  openai: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  local:  'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
}

function ProviderModal({
  initial,
  onClose,
  onSave,
}: {
  initial?: ModelProvider
  onClose: () => void
  onSave: (data: Partial<ModelProvider>) => void
}) {
  const { t } = useTranslation()
  const isEdit = !!initial

  const [name, setName] = useState(initial?.name ?? '')
  const [providerType, setProviderType] = useState<string>(initial?.provider_type ?? 'openai')
  const [baseUrl, setBaseUrl] = useState(initial?.base_url ?? '')
  const [apiKey, setApiKey] = useState(initial?.api_key ?? '')
  const [defaultModel, setDefaultModel] = useState(initial?.default_model ?? '')
  const [notes, setNotes] = useState(initial?.notes ?? '')
  const [showKey, setShowKey] = useState(false)

  const applyPreset = (presetKey: string) => {
    const p = PROVIDER_PRESETS[presetKey]
    if (!p) return
    setBaseUrl(p.base_url)
    if (!name) setName(p.label)
    if (presetKey === 'ollama') setProviderType('local')
    else setProviderType('openai')
  }

  const handleSave = () => {
    onSave({
      name,
      provider_type: providerType as ModelProvider['provider_type'],
      base_url: baseUrl || undefined,
      api_key: apiKey || undefined,
      default_model: defaultModel || undefined,
      notes: notes || undefined,
      enabled: initial?.enabled ?? true,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-lg">
        <div className="p-6 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-lg font-semibold dark:text-white">
            {isEdit ? t('providers.editTitle') : t('providers.addTitle')}
          </h2>
        </div>

        <div className="p-6 space-y-4">
          {/* Quick presets */}
          {!isEdit && (
            <div>
              <label className={labelCls}>{t('providers.quickPreset')}</label>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(PROVIDER_PRESETS).map(([key, p]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => applyPreset(key)}
                    className="px-2.5 py-1 text-xs rounded-full border border-blue-300 text-blue-600 hover:bg-blue-50 dark:border-blue-700 dark:text-blue-400 dark:hover:bg-blue-900/30 transition-colors"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Name */}
          <div>
            <label className={labelCls}>
              {t('common.name')} <span className="text-red-500">*</span>
            </label>
            <input
              className={inputCls}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('providers.namePlaceholder')}
            />
          </div>

          {/* Provider type */}
          <div>
            <label className={labelCls}>{t('providers.providerType')}</label>
            <select
              className={inputCls}
              value={providerType}
              onChange={(e) => setProviderType(e.target.value)}
            >
              {PROVIDER_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Base URL */}
          <div>
            <label className={labelCls}>
              Base URL
              <span className="ml-1 text-gray-400 font-normal text-[11px]">（OpenAI 兼容接口地址）</span>
            </label>
            <input
              className={inputCls}
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.example.com/v1"
            />
          </div>

          {/* API Key */}
          <div>
            <label className={labelCls}>API Key</label>
            <div className="relative">
              <input
                className={`${inputCls} pr-9`}
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          {/* Default model + Notes */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>{t('providers.defaultModel')}</label>
              <input
                className={inputCls}
                value={defaultModel}
                onChange={(e) => setDefaultModel(e.target.value)}
                placeholder="gpt-4o-mini"
              />
            </div>
            <div>
              <label className={labelCls}>{t('common.description')}</label>
              <input
                className={inputCls}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t('providers.notesPlaceholder')}
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
            onClick={handleSave}
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

export default function ProvidersPage() {
  const { t } = useTranslation()
  const [showAdd, setShowAdd] = useState(false)
  const [editProvider, setEditProvider] = useState<ModelProvider | null>(null)
  const qc = useQueryClient()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['providers'],
    queryFn: listProviders,
  })

  const createMut = useMutation({
    mutationFn: createProvider,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['providers'] }); setShowAdd(false); toast.success('模型服务商已保存') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '操作失败'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ModelProvider> }) => updateProvider(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['providers'] }); setEditProvider(null); toast.success('模型服务商已保存') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '操作失败'),
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => updateProvider(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['providers'] }),
  })

  const deleteMut = useMutation({
    mutationFn: deleteProvider,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['providers'] }); toast.success('已删除') },
    onError: (err) => toast.error(err instanceof Error ? err.message : '删除失败'),
  })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorAlert error={error as Error} onRetry={refetch} />

  const providers = data?.data ?? []

  return (
    <div>
      <PageHeader
        title={t('providers.title')}
        description={t('providers.description')}
        action={
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={16} /> {t('providers.addProvider')}
          </button>
        }
      />

      <Card padding={false}>
        <DataTable
          data={providers}
          keyFn={(p) => p.id}
          emptyMessage={t('providers.noProviders')}
          columns={[
            {
              key: 'name',
              header: t('common.name'),
              width: '200px',
              render: (p) => (
                <div>
                  <p className="font-medium dark:text-white">{p.name}</p>
                  {p.notes && <p className="text-xs text-gray-400">{p.notes}</p>}
                </div>
              ),
            },
            {
              key: 'type',
              header: t('providers.providerType'),
              width: '130px',
              render: (p) => (
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${PROCESSOR_COLORS[p.provider_type] ?? 'bg-gray-100 text-gray-700'}`}>
                  {p.provider_type}
                </span>
              ),
            },
            {
              key: 'base_url',
              header: 'Base URL',
              render: (p) => (
                <span className="text-xs font-mono text-gray-500 dark:text-gray-400">
                  {p.base_url ?? '—'}
                </span>
              ),
            },
            {
              key: 'model',
              header: t('providers.defaultModel'),
              width: '140px',
              render: (p) => (
                <span className="text-xs font-mono text-gray-600 dark:text-gray-300">
                  {p.default_model ?? '—'}
                </span>
              ),
            },
            {
              key: 'api_key',
              header: 'API Key',
              width: '100px',
              render: (p) => (
                <span className="text-xs text-gray-400">
                  {p.api_key ? '••••••••' : '—'}
                </span>
              ),
            },
            {
              key: 'status',
              header: t('common.status'),
              width: '70px',
              render: (p) => (
                <span className={`text-xs font-medium ${p.enabled ? 'text-green-600' : 'text-gray-400'}`}>
                  {p.enabled ? t('common.enabled') : t('common.disabled')}
                </span>
              ),
            },
            {
              key: 'actions',
              header: t('common.actions'),
              width: '160px',
              render: (p) => (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => toggleMut.mutate({ id: p.id, enabled: !p.enabled })}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500"
                  >
                    {p.enabled ? <ToggleRight size={12} /> : <ToggleLeft size={12} />}
                    {p.enabled ? t('common.disable') : t('common.enable')}
                  </button>
                  <button
                    onClick={() => setEditProvider(p)}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-blue-100 dark:hover:bg-blue-900/30 text-blue-600"
                  >
                    <Pencil size={12} />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(t('providers.confirmDelete', { name: p.name }))) deleteMut.mutate(p.id)
                    }}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ),
            },
          ]}
        />
      </Card>

      {showAdd && (
        <ProviderModal onClose={() => setShowAdd(false)} onSave={(d) => createMut.mutate(d)} />
      )}
      {editProvider && (
        <ProviderModal
          initial={editProvider}
          onClose={() => setEditProvider(null)}
          onSave={(d) => updateMut.mutate({ id: editProvider.id, data: d })}
        />
      )}
    </div>
  )
}
