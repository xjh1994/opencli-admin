import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listAgents, createAgent, updateAgent, deleteAgent } from '../api/endpoints'
import type { AIAgent } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import { Plus, Pencil, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'

const PROCESSOR_COLORS: Record<string, string> = {
  claude:  'bg-purple-100 text-purple-700',
  openai:  'bg-green-100 text-green-700',
  local:   'bg-orange-100 text-orange-700',
}

function ProcessorBadge({ type }: { type: string }) {
  const cls = PROCESSOR_COLORS[type] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {type}
    </span>
  )
}

const inputCls =
  'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'
const labelCls = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'

const PROCESSOR_TYPES = ['claude', 'openai', 'local'] as const

const DEFAULT_MODELS: Record<string, string> = {
  claude: 'claude-sonnet-4-6',
  openai: 'gpt-4o',
  local: 'llama3',
}

function AgentModal({
  initial,
  onClose,
  onSave,
}: {
  initial?: AIAgent
  onClose: () => void
  onSave: (data: Partial<AIAgent>) => void
}) {
  const { t } = useTranslation()
  const isEdit = !!initial

  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [processorType, setProcessorType] = useState<string>(initial?.processor_type ?? 'claude')
  const [model, setModel] = useState(initial?.model ?? DEFAULT_MODELS.claude)
  const [promptTemplate, setPromptTemplate] = useState(
    initial?.prompt_template ?? '请分析以下内容，提取关键信息并生成摘要：\n\n标题：{{title}}\n内容：{{content}}'
  )

  const handleProcessorChange = (type: string) => {
    setProcessorType(type)
    if (!isEdit) setModel(DEFAULT_MODELS[type] ?? '')
  }

  const handleSubmit = () => {
    onSave({
      name,
      description: description || undefined,
      processor_type: processorType as AIAgent['processor_type'],
      model: model || undefined,
      prompt_template: promptTemplate,
      enabled: initial?.enabled ?? true,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="p-6 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-lg font-semibold dark:text-white">
            {isEdit ? t('agents.editTitle') : t('agents.addTitle')}
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
                onChange={(e) => setName(e.target.value)}
                placeholder="内容摘要助手"
              />
            </div>
            <div>
              <label className={labelCls}>{t('agents.processorType')}</label>
              <select
                className={inputCls}
                value={processorType}
                onChange={(e) => handleProcessorChange(e.target.value)}
              >
                {PROCESSOR_TYPES.map((type) => (
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
              placeholder={t('agents.descriptionPlaceholder')}
            />
          </div>

          <div>
            <label className={labelCls}>{t('agents.model')}</label>
            <input
              className={inputCls}
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={DEFAULT_MODELS[processorType] ?? ''}
            />
          </div>

          <div>
            <label className={labelCls}>
              {t('agents.promptTemplate')} <span className="text-red-500">*</span>
            </label>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
              {t('agents.promptHint')}
            </p>
            <textarea
              className={`${inputCls} font-mono text-xs`}
              rows={8}
              value={promptTemplate}
              onChange={(e) => setPromptTemplate(e.target.value)}
              placeholder="请分析以下内容：\n\n{{title}}\n{{content}}"
            />
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
            disabled={!name.trim() || !promptTemplate.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {isEdit ? t('common.save') : t('common.create')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function AgentsPage() {
  const { t } = useTranslation()
  const [showAdd, setShowAdd] = useState(false)
  const [editAgent, setEditAgent] = useState<AIAgent | null>(null)
  const qc = useQueryClient()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['agents'],
    queryFn: () => listAgents(),
  })

  const createMut = useMutation({
    mutationFn: createAgent,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agents'] }); setShowAdd(false) },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<AIAgent> }) => updateAgent(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agents'] }); setEditAgent(null) },
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => updateAgent(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agents'] }),
  })

  const deleteMut = useMutation({
    mutationFn: deleteAgent,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agents'] }),
  })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorAlert error={error as Error} onRetry={refetch} />

  const agents = data?.data ?? []

  return (
    <div>
      <PageHeader
        title={t('agents.title')}
        description={t('agents.description')}
        action={
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={16} /> {t('agents.addAgent')}
          </button>
        }
      />

      <Card padding={false}>
        <DataTable
          data={agents}
          keyFn={(a) => a.id}
          emptyMessage={t('agents.noAgents')}
          columns={[
            {
              key: 'name',
              header: t('common.name'),
              width: '200px',
              render: (a) => (
                <div>
                  <p className="font-medium">{a.name}</p>
                  {a.description && <p className="text-xs text-gray-400">{a.description}</p>}
                </div>
              ),
            },
            {
              key: 'type',
              header: t('agents.processorType'),
              width: '90px',
              render: (a) => <ProcessorBadge type={a.processor_type} />,
            },
            {
              key: 'model',
              header: t('agents.model'),
              width: '160px',
              render: (a) => (
                <span className="text-xs font-mono text-gray-600 dark:text-gray-300">
                  {a.model ?? '—'}
                </span>
              ),
            },
            {
              key: 'prompt',
              header: t('agents.promptTemplate'),
              render: (a) => (
                <p className="text-xs text-gray-500 truncate max-w-xs">
                  {a.prompt_template || '—'}
                </p>
              ),
            },
            {
              key: 'status',
              header: t('common.status'),
              width: '70px',
              render: (a) => (
                <span className={`text-xs font-medium ${a.enabled ? 'text-green-600' : 'text-gray-400'}`}>
                  {a.enabled ? t('common.enabled') : t('common.disabled')}
                </span>
              ),
            },
            {
              key: 'actions',
              header: t('common.actions'),
              width: '160px',
              render: (a) => (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => toggleMut.mutate({ id: a.id, enabled: !a.enabled })}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500"
                  >
                    {a.enabled ? <ToggleRight size={12} /> : <ToggleLeft size={12} />}
                    {a.enabled ? t('common.disable') : t('common.enable')}
                  </button>
                  <button
                    onClick={() => setEditAgent(a)}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-blue-100 dark:hover:bg-blue-900/30 text-blue-600"
                  >
                    <Pencil size={12} /> 编辑
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(t('agents.confirmDelete', { name: a.name }))) deleteMut.mutate(a.id)
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
        <AgentModal onClose={() => setShowAdd(false)} onSave={(d) => createMut.mutate(d)} />
      )}

      {editAgent && (
        <AgentModal
          initial={editAgent}
          onClose={() => setEditAgent(null)}
          onSave={(d) => updateMut.mutate({ id: editAgent.id, data: d })}
        />
      )}
    </div>
  )
}
