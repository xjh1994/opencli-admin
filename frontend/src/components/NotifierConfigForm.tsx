import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Trash2, Plus } from 'lucide-react'

// ── helpers ───────────────────────────────────────────────────────────────────

const input =
  'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'
const labelCls = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'
const hintCls = 'mt-1 text-xs text-gray-400'

function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string
  hint?: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <div>
      <label className={labelCls}>
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {hint && <p className={hintCls}>{hint}</p>}
    </div>
  )
}

function TextInput({
  value,
  onChange,
  placeholder,
  type = 'text',
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  type?: string
}) {
  return (
    <input
      type={type}
      className={input}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
    />
  )
}

function TextareaInput({
  value,
  onChange,
  placeholder,
  rows = 3,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  rows?: number
}) {
  return (
    <textarea
      className={`${input} resize-y`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
    />
  )
}

type KVPair = { key: string; value: string }

function KVList({
  pairs,
  onChange,
  keyPlaceholder,
  valuePlaceholder,
}: {
  pairs: KVPair[]
  onChange: (pairs: KVPair[]) => void
  keyPlaceholder?: string
  valuePlaceholder?: string
}) {
  const update = (i: number, field: 'key' | 'value', v: string) =>
    onChange(pairs.map((p, idx) => (idx === i ? { ...p, [field]: v } : p)))
  const remove = (i: number) => onChange(pairs.filter((_, idx) => idx !== i))

  return (
    <div className="space-y-2">
      {pairs.map((p, i) => (
        <div key={i} className="flex gap-2 items-center">
          <input
            className={`${input} flex-1`}
            value={p.key}
            onChange={(e) => update(i, 'key', e.target.value)}
            placeholder={keyPlaceholder ?? 'key'}
          />
          <input
            className={`${input} flex-1`}
            value={p.value}
            onChange={(e) => update(i, 'value', e.target.value)}
            placeholder={valuePlaceholder ?? 'value'}
          />
          <button
            type="button"
            onClick={() => remove(i)}
            className="p-1.5 text-red-400 hover:text-red-600 flex-shrink-0"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...pairs, { key: '', value: '' }])}
        className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 mt-1"
      >
        <Plus size={12} /> Add row
      </button>
    </div>
  )
}

function kvToObj(pairs: KVPair[]): Record<string, string> {
  return Object.fromEntries(pairs.filter((p) => p.key).map((p) => [p.key, p.value]))
}

function objToKv(obj: Record<string, unknown> | undefined): KVPair[] {
  if (!obj) return []
  return Object.entries(obj).map(([key, value]) => ({ key, value: String(value) }))
}

// ── Per-type config forms ─────────────────────────────────────────────────────

function WebhookConfig({
  config,
  onChange,
}: {
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  const [headers, setHeaders] = useState<KVPair[]>(
    objToKv(config.headers as Record<string, unknown>),
  )

  const update = (patch: Partial<Record<string, unknown>>) => onChange({ ...config, ...patch })

  const updateHeaders = (pairs: KVPair[]) => {
    setHeaders(pairs)
    update({ headers: kvToObj(pairs) })
  }

  return (
    <div className="space-y-3">
      <Field label={t('notifierConfig.webhookUrl')} required>
        <TextInput
          value={(config.url as string) ?? ''}
          onChange={(v) => update({ url: v })}
          placeholder="https://hooks.example.com/notify"
        />
      </Field>
      <Field label={t('notifierConfig.secret')} hint={t('notifierConfig.webhookSecretHint')}>
        <TextInput
          value={(config.secret as string) ?? ''}
          onChange={(v) => update({ secret: v })}
          placeholder={t('notifierConfig.optional')}
          type="password"
        />
      </Field>
      <Field label={t('notifierConfig.extraHeaders')}>
        <KVList
          pairs={headers}
          onChange={updateHeaders}
          keyPlaceholder="Header-Name"
          valuePlaceholder="value"
        />
      </Field>
    </div>
  )
}

function DingTalkConfig({
  config,
  onChange,
}: {
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  const update = (patch: Partial<Record<string, unknown>>) => onChange({ ...config, ...patch })

  return (
    <div className="space-y-3">
      <Field label={t('notifierConfig.webhookUrl')} hint={t('notifierConfig.dingtalkUrlHint')} required>
        <TextInput
          value={(config.webhook_url as string) ?? ''}
          onChange={(v) => update({ webhook_url: v })}
          placeholder="https://oapi.dingtalk.com/robot/send?access_token=..."
        />
      </Field>
      <Field label={t('notifierConfig.secret')} hint={t('notifierConfig.dingtalkSecretHint')}>
        <TextInput
          value={(config.secret as string) ?? ''}
          onChange={(v) => update({ secret: v })}
          placeholder={t('notifierConfig.optional')}
          type="password"
        />
      </Field>
      <Field label={t('notifierConfig.titleTemplate')} hint={t('notifierConfig.templateHint')}>
        <TextInput
          value={(config.title as string) ?? ''}
          onChange={(v) => update({ title: v })}
          placeholder="New record: {{title}}"
        />
      </Field>
      <Field label={t('notifierConfig.contentTemplate')} hint={t('notifierConfig.templateHint')}>
        <TextareaInput
          value={(config.content as string) ?? ''}
          onChange={(v) => update({ content: v })}
          placeholder={'Source: {{source_id}}\n{{title}}'}
        />
      </Field>
    </div>
  )
}

function FeishuConfig({
  config,
  onChange,
}: {
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  const update = (patch: Partial<Record<string, unknown>>) => onChange({ ...config, ...patch })

  return (
    <div className="space-y-3">
      <Field label={t('notifierConfig.webhookUrl')} hint={t('notifierConfig.feishuUrlHint')} required>
        <TextInput
          value={(config.webhook_url as string) ?? ''}
          onChange={(v) => update({ webhook_url: v })}
          placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
        />
      </Field>
      <Field label={t('notifierConfig.secret')} hint={t('notifierConfig.feishuSecretHint')}>
        <TextInput
          value={(config.secret as string) ?? ''}
          onChange={(v) => update({ secret: v })}
          placeholder={t('notifierConfig.optional')}
          type="password"
        />
      </Field>
      <Field label={t('notifierConfig.titleTemplate')} hint={t('notifierConfig.templateHint')}>
        <TextInput
          value={(config.title as string) ?? ''}
          onChange={(v) => update({ title: v })}
          placeholder="【新采集】{{title}}"
        />
      </Field>
      <Field label={t('notifierConfig.contentTemplate')} hint={t('notifierConfig.templateHint')}>
        <TextareaInput
          value={(config.content as string) ?? ''}
          onChange={(v) => update({ content: v })}
          placeholder={'**来源**：{{source_id}}\n**标题**：{{title}}\n**链接**：{{url}}'}
        />
      </Field>
    </div>
  )
}

function WeComConfig({
  config,
  onChange,
}: {
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  const update = (patch: Partial<Record<string, unknown>>) => onChange({ ...config, ...patch })

  return (
    <div className="space-y-3">
      <Field label={t('notifierConfig.webhookUrl')} hint={t('notifierConfig.wecomUrlHint')} required>
        <TextInput
          value={(config.webhook_url as string) ?? ''}
          onChange={(v) => update({ webhook_url: v })}
          placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
        />
      </Field>
      <Field label={t('notifierConfig.contentTemplate')} hint={t('notifierConfig.templateHint')}>
        <TextareaInput
          value={(config.content as string) ?? ''}
          onChange={(v) => update({ content: v })}
          placeholder={'**{{title}}**\nSource: {{source_id}}'}
        />
      </Field>
    </div>
  )
}

function EmailConfig({
  config,
  onChange,
}: {
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  const update = (patch: Partial<Record<string, unknown>>) => onChange({ ...config, ...patch })

  // to is stored as string[] in backend; edit as comma-separated string
  const toValue = Array.isArray(config.to) ? (config.to as string[]).join(', ') : (config.to as string) ?? ''

  const updateTo = (v: string) => {
    const arr = v.split(',').map((s) => s.trim()).filter(Boolean)
    update({ to: arr })
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('notifierConfig.smtpHost')} required>
          <TextInput
            value={(config.smtp_host as string) ?? ''}
            onChange={(v) => update({ smtp_host: v })}
            placeholder="smtp.gmail.com"
          />
        </Field>
        <Field label={t('notifierConfig.smtpPort')}>
          <TextInput
            value={config.smtp_port != null ? String(config.smtp_port) : ''}
            onChange={(v) => update({ smtp_port: v ? Number(v) : undefined })}
            placeholder="587"
            type="number"
          />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('notifierConfig.smtpUser')}>
          <TextInput
            value={(config.smtp_user as string) ?? ''}
            onChange={(v) => update({ smtp_user: v })}
            placeholder="user@gmail.com"
          />
        </Field>
        <Field label={t('notifierConfig.smtpPassword')}>
          <TextInput
            value={(config.smtp_password as string) ?? ''}
            onChange={(v) => update({ smtp_password: v })}
            placeholder={t('notifierConfig.optional')}
            type="password"
          />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('notifierConfig.fromAddr')}>
          <TextInput
            value={(config.from as string) ?? ''}
            onChange={(v) => update({ from: v })}
            placeholder="noreply@example.com"
          />
        </Field>
        <Field label={t('notifierConfig.toAddrs')} hint={t('notifierConfig.toAddrsHint')} required>
          <TextInput
            value={toValue}
            onChange={updateTo}
            placeholder="a@example.com, b@example.com"
          />
        </Field>
      </div>
      <Field label={t('notifierConfig.subjectTemplate')} hint={t('notifierConfig.templateHint')}>
        <TextInput
          value={(config.subject as string) ?? ''}
          onChange={(v) => update({ subject: v })}
          placeholder="New record: {{title}}"
        />
      </Field>
      <Field label={t('notifierConfig.bodyTemplate')} hint={t('notifierConfig.templateHint')}>
        <TextareaInput
          value={(config.body as string) ?? ''}
          onChange={(v) => update({ body: v })}
          placeholder={'Source: {{source_id}}\nTitle: {{title}}\nURL: {{url}}'}
        />
      </Field>
    </div>
  )
}

// ── Public component ──────────────────────────────────────────────────────────

export type NotifierType = 'webhook' | 'dingtalk' | 'feishu' | 'wecom' | 'email'

interface Props {
  notifierType: NotifierType
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
}

export default function NotifierConfigForm({ notifierType, config, onChange }: Props) {
  switch (notifierType) {
    case 'webhook':
      return <WebhookConfig config={config} onChange={onChange} />
    case 'dingtalk':
      return <DingTalkConfig config={config} onChange={onChange} />
    case 'feishu':
      return <FeishuConfig config={config} onChange={onChange} />
    case 'wecom':
      return <WeComConfig config={config} onChange={onChange} />
    case 'email':
      return <EmailConfig config={config} onChange={onChange} />
  }
}
