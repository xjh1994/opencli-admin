import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  listNotificationRules,
  createNotificationRule,
  deleteNotificationRule,
  listNotificationLogs,
} from '../api/endpoints'
import type { NotificationRule, NotificationLog } from '../api/types'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import { Plus, Trash2 } from 'lucide-react'
import { formatInTimeZone } from 'date-fns-tz'

const NOTIFIER_TYPES = ['webhook', 'email', 'feishu', 'dingtalk', 'wecom']
const TRIGGER_EVENTS = ['on_new_record', 'on_ai_processed', 'on_task_failed']

function AddRuleModal({ onClose, onSave }: { onClose: () => void; onSave: (d: Partial<NotificationRule>) => void }) {
  const { t } = useTranslation()
  const [form, setForm] = useState({ name: '', trigger_event: 'on_new_record', notifier_type: 'webhook', enabled: true })
  const [configJson, setConfigJson] = useState('{"url": "https://hooks.example.com/notify"}')
  const [jsonError, setJsonError] = useState('')

  const inputCls = 'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white'
  const labelCls = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'

  const handleSubmit = () => {
    try {
      const config = JSON.parse(configJson)
      setJsonError('')
      onSave({ ...form, notifier_config: config })
    } catch {
      setJsonError('Invalid JSON')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-4 dark:text-white">{t('notifications.addRuleTitle')}</h2>
        <div className="space-y-4">
          <div>
            <label className={labelCls}>{t('common.name')}</label>
            <input className={inputCls} value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div>
            <label className={labelCls}>{t('notifications.triggerEvent')}</label>
            <select className={inputCls} value={form.trigger_event}
              onChange={(e) => setForm((f) => ({ ...f, trigger_event: e.target.value }))}>
              {TRIGGER_EVENTS.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
          </div>
          <div>
            <label className={labelCls}>{t('notifications.notifierType')}</label>
            <select className={inputCls} value={form.notifier_type}
              onChange={(e) => setForm((f) => ({ ...f, notifier_type: e.target.value }))}>
              {NOTIFIER_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </div>
          <div>
            <label className={labelCls}>{t('notifications.notifierConfig')}</label>
            <textarea className={`${inputCls} font-mono`} rows={4}
              value={configJson} onChange={(e) => setConfigJson(e.target.value)} />
            {jsonError && <p className="mt-1 text-xs text-red-500">{jsonError}</p>}
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600">
            {t('common.cancel')}
          </button>
          <button onClick={handleSubmit} className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700">
            {t('common.create')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function NotificationsPage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<'rules' | 'logs'>('rules')
  const [showAdd, setShowAdd] = useState(false)
  const qc = useQueryClient()

  const rulesQ = useQuery({ queryKey: ['notification-rules'], queryFn: listNotificationRules })
  const logsQ = useQuery({ queryKey: ['notification-logs'], queryFn: () => listNotificationLogs() })

  const createMut = useMutation({
    mutationFn: createNotificationRule,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['notification-rules'] }); setShowAdd(false) },
  })

  const deleteMut = useMutation({
    mutationFn: deleteNotificationRule,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notification-rules'] }),
  })

  const rules: NotificationRule[] = rulesQ.data?.data ?? []
  const logs: NotificationLog[] = logsQ.data?.data ?? []

  return (
    <div>
      <PageHeader
        title={t('notifications.title')}
        description={t('notifications.description')}
        action={
          tab === 'rules' && (
            <button onClick={() => setShowAdd(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
              <Plus size={16} /> {t('notifications.addRule')}
            </button>
          )
        }
      />

      <div className="flex gap-2 mb-4">
        {(['rules', 'logs'] as const).map((tabKey) => (
          <button key={tabKey} onClick={() => setTab(tabKey)}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
              tab === tabKey ? 'bg-blue-600 text-white' : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 hover:bg-gray-50'
            }`}>
            {tabKey === 'rules' ? t('notifications.tabRules') : t('notifications.tabLogs')}
          </button>
        ))}
      </div>

      {tab === 'rules' && (
        rulesQ.isLoading ? <PageLoader /> :
        rulesQ.error ? <ErrorAlert error={rulesQ.error as Error} /> :
        <Card padding={false}>
          <DataTable
            data={rules}
            keyFn={(r) => r.id}
            emptyMessage={t('notifications.noRules')}
            columns={[
              { key: 'name', header: t('common.name'), render: (r) => <span className="font-medium">{r.name}</span> },
              { key: 'event', header: t('notifications.triggerEvent'), render: (r) => <code className="text-xs bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded">{r.trigger_event}</code> },
              { key: 'type', header: t('notifications.notifierType'), render: (r) => <span className="text-xs">{r.notifier_type}</span> },
              { key: 'enabled', header: t('common.status'), render: (r) => <StatusBadge status={r.enabled ? 'online' : 'offline'} /> },
              {
                key: 'id', header: t('common.id'), width: '100px',
                render: (r) => <span className="font-mono text-xs text-gray-400">{r.id.slice(0, 8)}</span>,
              },
              {
                key: 'created_at', header: t('common.createdAt'), width: '130px',
                render: (r) => <span className="text-xs text-gray-500">{formatInTimeZone(new Date(r.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}</span>,
              },
              {
                key: 'updated_at', header: t('common.updatedAt'), width: '130px',
                render: (r) => <span className="text-xs text-gray-500">{formatInTimeZone(new Date(r.updated_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}</span>,
              },
              {
                key: 'actions', header: t('common.actions'), width: '70px',
                render: (r) => (
                  <button onClick={() => { if (confirm(t('notifications.confirmDelete', { name: r.name }))) deleteMut.mutate(r.id) }}
                    className="p-1.5 rounded hover:bg-red-100 text-red-500">
                    <Trash2 size={14} />
                  </button>
                ),
              },
            ]}
          />
        </Card>
      )}

      {tab === 'logs' && (
        logsQ.isLoading ? <PageLoader /> :
        logsQ.error ? <ErrorAlert error={logsQ.error as Error} /> :
        <Card padding={false}>
          <DataTable
            data={logs}
            keyFn={(l) => l.id}
            emptyMessage={t('notifications.noLogs')}
            columns={[
              {
                key: 'id', header: t('common.id'), width: '100px',
                render: (l) => <span className="font-mono text-xs text-gray-400">{l.id.slice(0, 8)}</span>,
              },
              { key: 'rule', header: t('notifications.ruleId'), render: (l) => <span className="font-mono text-xs">{l.rule_id.slice(0, 12)}…</span> },
              { key: 'status', header: t('common.status'), render: (l) => <StatusBadge status={l.status} /> },
              { key: 'error', header: t('notifications.errorMsg'), render: (l) => <span className="text-xs text-red-400">{l.error_message || '—'}</span> },
              {
                key: 'created_at', header: t('common.createdAt'), width: '130px',
                render: (l) => <span className="text-xs text-gray-500">{formatInTimeZone(new Date(l.created_at), 'Asia/Shanghai', 'MM-dd HH:mm:ss')}</span>,
              },
            ]}
          />
        </Card>
      )}

      {showAdd && <AddRuleModal onClose={() => setShowAdd(false)} onSave={(d) => createMut.mutate(d)} />}
    </div>
  )
}
