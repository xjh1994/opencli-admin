import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listSchedules, createSchedule, updateSchedule, deleteSchedule } from '../api/endpoints'
import type { CronSchedule } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import { Plus, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'
import { formatInTimeZone } from 'date-fns-tz'

function AddScheduleModal({
  onClose,
  onSave,
}: {
  onClose: () => void
  onSave: (data: Partial<CronSchedule>) => void
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState({
    source_id: '',
    name: '',
    cron_expression: '0 * * * *',
    timezone: 'UTC',
  })

  const inputCls = 'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white'
  const labelCls = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-4 dark:text-white">{t('schedules.addScheduleTitle')}</h2>
        <div className="space-y-4">
          {[
            { label: t('schedules.sourceId'), key: 'source_id', placeholder: 'UUID of the data source' },
            { label: t('common.name'),         key: 'name',        placeholder: 'Daily at 9am' },
            { label: t('schedules.cronExpression'), key: 'cron_expression', placeholder: '0 9 * * *' },
            { label: t('schedules.timezone'),  key: 'timezone',    placeholder: 'Asia/Shanghai' },
          ].map(({ label, key, placeholder }) => (
            <div key={key}>
              <label className={labelCls}>{label}</label>
              <input
                className={inputCls}
                value={(form as Record<string, string>)[key]}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                placeholder={placeholder}
              />
            </div>
          ))}
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600">
            {t('common.cancel')}
          </button>
          <button onClick={() => onSave(form)} className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700">
            {t('common.create')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function SchedulesPage() {
  const { t } = useTranslation()
  const [showAdd, setShowAdd] = useState(false)
  const qc = useQueryClient()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['schedules'],
    queryFn: () => listSchedules(),
  })

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
            { key: 'name', header: t('common.name'), render: (s) => <span className="font-medium">{s.name}</span> },
            {
              key: 'cron',
              header: t('schedules.cronExpression'),
              render: (s) => (
                <code className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs font-mono">
                  {s.cron_expression}
                </code>
              ),
            },
            { key: 'tz', header: t('schedules.timezone'), render: (s) => <span className="text-xs">{s.timezone}</span> },
            {
              key: 'last_run',
              header: t('schedules.lastRun'),
              render: (s) => (
                <span className="text-xs text-gray-500">
                  {s.last_run_at
                    ? formatInTimeZone(new Date(s.last_run_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')
                    : '—'}
                </span>
              ),
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
              key: 'status',
              header: t('schedules.enabledCol'),
              render: (s) => (
                <span className={`text-xs font-medium ${s.enabled ? 'text-green-600' : 'text-gray-400'}`}>
                  {s.enabled ? t('common.yes') : t('common.no')}
                </span>
              ),
              width: '80px',
            },
            {
              key: 'actions',
              header: t('common.actions'),
              width: '90px',
              render: (s) => (
                <div className="flex gap-2">
                  <button onClick={() => toggleMut.mutate({ id: s.id, enabled: !s.enabled })}
                    className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500">
                    {s.enabled ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                  </button>
                  <button
                    onClick={() => { if (confirm(t('schedules.confirmDelete', { name: s.name }))) deleteMut.mutate(s.id) }}
                    className="p-1.5 rounded hover:bg-red-100 text-red-500">
                    <Trash2 size={14} />
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
