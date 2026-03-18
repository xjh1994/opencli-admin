import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2 } from 'lucide-react'

// ── helpers ──────────────────────────────────────────────────────────────────

const input =
  'w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'
const label = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'
const hint = 'mt-1 text-xs text-gray-400'

function Field({
  label: l,
  hint: h,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className={label}>{l}</label>
      {children}
      {h && <p className={hint}>{h}</p>}
    </div>
  )
}

function TextInput({
  value,
  onChange,
  placeholder,
  required,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  required?: boolean
}) {
  return (
    <input
      className={input}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      required={required}
    />
  )
}

function NumberInput({
  value,
  onChange,
  placeholder,
  min,
}: {
  value: number | ''
  onChange: (v: number | '') => void
  placeholder?: string
  min?: number
}) {
  return (
    <input
      type="number"
      className={input}
      value={value}
      min={min}
      onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
      placeholder={placeholder}
    />
  )
}

function SelectInput({
  value,
  onChange,
  options,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <select className={input} value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

// Key-value pair list (for selectors / headers / params / args / defaults)
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

// ── Per-channel config forms ──────────────────────────────────────────────────

function RSSConfig({
  config,
  onChange,
}: {
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  return (
    <div className="space-y-3">
      <Field label={t('channelConfig.feedUrl')}>
        <TextInput
          value={(config.feed_url as string) ?? ''}
          onChange={(v) => onChange({ ...config, feed_url: v })}
          placeholder="https://hnrss.org/frontpage"
          required
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('channelConfig.maxEntries')} hint={t('channelConfig.maxEntriesHint')}>
          <NumberInput
            value={(config.max_entries as number) ?? ''}
            onChange={(v) => onChange({ ...config, max_entries: v === '' ? undefined : v })}
            placeholder="50"
            min={1}
          />
        </Field>
        <Field label={t('channelConfig.timeout')} hint={t('channelConfig.timeoutHint')}>
          <NumberInput
            value={(config.timeout as number) ?? ''}
            onChange={(v) => onChange({ ...config, timeout: v === '' ? undefined : v })}
            placeholder="30"
            min={1}
          />
        </Field>
      </div>
    </div>
  )
}

function APIConfig({
  config,
  onChange,
}: {
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  const auth = (config.auth as Record<string, string>) ?? {}
  const authType = auth.type ?? 'none'
  const [params, setParams] = useState<KVPair[]>(objToKv(config.params as Record<string, unknown>))
  const [headers, setHeaders] = useState<KVPair[]>(objToKv(config.headers as Record<string, unknown>))

  const update = (patch: Partial<Record<string, unknown>>) => onChange({ ...config, ...patch })

  const updateParams = (pairs: KVPair[]) => {
    setParams(pairs)
    update({ params: kvToObj(pairs) })
  }

  const updateHeaders = (pairs: KVPair[]) => {
    setHeaders(pairs)
    update({ headers: kvToObj(pairs) })
  }

  const updateAuth = (patch: Partial<Record<string, string>>) =>
    update({ auth: { ...auth, ...patch } })

  return (
    <div className="space-y-3">
      <Field label={t('channelConfig.baseUrl')}>
        <TextInput
          value={(config.base_url as string) ?? ''}
          onChange={(v) => update({ base_url: v })}
          placeholder="https://api.github.com"
          required
        />
      </Field>
      <div className="grid grid-cols-3 gap-3">
        <Field label={t('channelConfig.endpoint')} hint={t('channelConfig.endpointHint')}>
          <TextInput
            value={(config.endpoint as string) ?? ''}
            onChange={(v) => update({ endpoint: v })}
            placeholder="/repos/owner/repo/issues"
            required
          />
        </Field>
        <Field label={t('channelConfig.method')}>
          <SelectInput
            value={(config.method as string) ?? 'GET'}
            onChange={(v) => update({ method: v })}
            options={['GET', 'POST', 'PUT', 'PATCH'].map((m) => ({ value: m, label: m }))}
          />
        </Field>
        <Field label={t('channelConfig.resultPath')} hint={t('channelConfig.resultPathHint')}>
          <TextInput
            value={(config.result_path as string) ?? ''}
            onChange={(v) => update({ result_path: v })}
            placeholder="data.items"
          />
        </Field>
      </div>

      <Field label={t('channelConfig.authType')}>
        <SelectInput
          value={authType}
          onChange={(v) => update({ auth: { type: v } })}
          options={[
            { value: 'none', label: t('channelConfig.authNone') },
            { value: 'bearer', label: t('channelConfig.authBearer') },
            { value: 'basic', label: t('channelConfig.authBasic') },
            { value: 'api_key', label: t('channelConfig.authApiKey') },
          ]}
        />
      </Field>

      {authType === 'bearer' && (
        <Field label={t('channelConfig.tokenEnvVar')} hint={t('channelConfig.tokenEnvVarHint')}>
          <TextInput
            value={auth.token_env ?? ''}
            onChange={(v) => updateAuth({ token_env: v })}
            placeholder="GITHUB_TOKEN"
          />
        </Field>
      )}
      {authType === 'basic' && (
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('channelConfig.username')} hint={t('channelConfig.usernameHint')}>
            <TextInput
              value={auth.username ?? ''}
              onChange={(v) => updateAuth({ username: v })}
              placeholder="{{secret:API_USER}}"
            />
          </Field>
          <Field label={t('channelConfig.password')} hint={t('channelConfig.passwordHint')}>
            <TextInput
              value={auth.password ?? ''}
              onChange={(v) => updateAuth({ password: v })}
              placeholder="{{secret:API_PASS}}"
            />
          </Field>
        </div>
      )}
      {authType === 'api_key' && (
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('channelConfig.headerName')}>
            <TextInput
              value={auth.header ?? 'X-API-Key'}
              onChange={(v) => updateAuth({ header: v })}
              placeholder="X-API-Key"
            />
          </Field>
          <Field label={t('channelConfig.keyEnvVar')}>
            <TextInput
              value={auth.key_env ?? ''}
              onChange={(v) => updateAuth({ key_env: v })}
              placeholder="MY_API_KEY"
            />
          </Field>
        </div>
      )}

      <Field label={t('channelConfig.queryParams')}>
        <KVList pairs={params} onChange={updateParams} keyPlaceholder="param" valuePlaceholder="value" />
      </Field>
      <Field label={t('channelConfig.extraHeaders')} hint={t('channelConfig.extraHeadersHint')}>
        <KVList pairs={headers} onChange={updateHeaders} keyPlaceholder="Header-Name" valuePlaceholder="value" />
      </Field>
      <Field label={t('channelConfig.timeout')}>
        <NumberInput
          value={(config.timeout as number) ?? ''}
          onChange={(v) => update({ timeout: v === '' ? undefined : v })}
          placeholder="30"
          min={1}
        />
      </Field>
    </div>
  )
}

function WebScraperConfig({
  config,
  onChange,
}: {
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  const [selectors, setSelectors] = useState<KVPair[]>(
    objToKv(config.selectors as Record<string, unknown>),
  )

  const update = (patch: Partial<Record<string, unknown>>) => onChange({ ...config, ...patch })

  const updateSelectors = (pairs: KVPair[]) => {
    setSelectors(pairs)
    update({ selectors: kvToObj(pairs) })
  }

  return (
    <div className="space-y-3">
      <Field label={t('channelConfig.url')}>
        <TextInput
          value={(config.url as string) ?? ''}
          onChange={(v) => update({ url: v })}
          placeholder="https://news.ycombinator.com"
          required
        />
      </Field>
      <Field
        label={t('channelConfig.listSelector')}
        hint={t('channelConfig.listSelectorHint')}
      >
        <TextInput
          value={(config.list_selector as string) ?? ''}
          onChange={(v) => update({ list_selector: v })}
          placeholder=".athing"
        />
      </Field>
      <Field label={t('channelConfig.fieldSelectors')} hint={t('channelConfig.fieldSelectorsHint')}>
        <KVList
          pairs={selectors}
          onChange={updateSelectors}
          keyPlaceholder="field name"
          valuePlaceholder="CSS selector"
        />
      </Field>
      <Field label={t('channelConfig.timeout')}>
        <NumberInput
          value={(config.timeout as number) ?? ''}
          onChange={(v) => update({ timeout: v === '' ? undefined : v })}
          placeholder="30"
          min={1}
        />
      </Field>
    </div>
  )
}

function CLIConfig({
  config,
  onChange,
}: {
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  const cmdArr = (config.command as string[]) ?? []
  const [cmdStr, setCmdStr] = useState(cmdArr.join(' '))
  const [defaults, setDefaults] = useState<KVPair[]>(
    objToKv(config.defaults as Record<string, unknown>),
  )
  const [envVars, setEnvVars] = useState<KVPair[]>(
    objToKv(config.env as Record<string, unknown>),
  )

  const update = (patch: Partial<Record<string, unknown>>) => onChange({ ...config, ...patch })

  const updateCmd = (v: string) => {
    setCmdStr(v)
    // Split respecting quoted strings
    const parts = v.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) ?? []
    update({ command: parts })
  }

  const updateDefaults = (pairs: KVPair[]) => {
    setDefaults(pairs)
    update({ defaults: kvToObj(pairs) })
  }

  const updateEnv = (pairs: KVPair[]) => {
    setEnvVars(pairs)
    update({ env: kvToObj(pairs) })
  }

  return (
    <div className="space-y-3">
      <Field label={t('channelConfig.binary')} hint={t('channelConfig.binaryHint')}>
        <TextInput
          value={(config.binary as string) ?? ''}
          onChange={(v) => update({ binary: v })}
          placeholder="curl"
          required
        />
      </Field>
      <Field
        label={t('channelConfig.arguments')}
        hint={t('channelConfig.argumentsHint')}
      >
        <TextInput
          value={cmdStr}
          onChange={updateCmd}
          placeholder="-s https://api.example.com/data/{{page}}"
          required
        />
      </Field>
      <Field label={t('channelConfig.outputFormat')}>
        <SelectInput
          value={(config.output_format as string) ?? 'json'}
          onChange={(v) => update({ output_format: v })}
          options={[
            { value: 'json', label: t('channelConfig.outputJson') },
            { value: 'text', label: t('channelConfig.outputText') },
          ]}
        />
      </Field>
      <Field label={t('channelConfig.templateDefaults')} hint={t('channelConfig.templateDefaultsHint')}>
        <KVList pairs={defaults} onChange={updateDefaults} keyPlaceholder="key" valuePlaceholder="default value" />
      </Field>
      <Field label={t('channelConfig.envVars')}>
        <KVList pairs={envVars} onChange={updateEnv} keyPlaceholder="VAR_NAME" valuePlaceholder="value" />
      </Field>
      <Field label={t('channelConfig.timeout')}>
        <NumberInput
          value={(config.timeout as number) ?? ''}
          onChange={(v) => update({ timeout: v === '' ? undefined : v })}
          placeholder="60"
          min={1}
        />
      </Field>
    </div>
  )
}

// ── OpenCLI presets ──────────────────────────────────────────────────────────

type Preset = {
  label: string
  group: string
  site: string
  command: string
  args: Record<string, string>
}

const OPENCLI_PRESETS: Preset[] = [
  // Public – no browser login required
  { group: '🌐 Public', label: 'Hacker News · top stories',   site: 'hackernews',   command: 'top',       args: { limit: '20' } },
  { group: '🌐 Public', label: 'BBC · latest news',           site: 'bbc',          command: 'news',      args: { limit: '20' } },
  { group: '🌐 Public', label: 'Reuters · search',            site: 'reuters',      command: 'search',    args: { query: 'technology', limit: '20' } },
  { group: '🌐 Public', label: 'GitHub · search repos',       site: 'github',       command: 'search',    args: { query: 'trending', limit: '20' } },
  // Chinese
  { group: '🇨🇳 国内',  label: 'Bilibili · 热门视频',         site: 'bilibili',     command: 'hot',       args: { limit: '20' } },
  { group: '🇨🇳 国内',  label: 'Bilibili · 动态',             site: 'bilibili',     command: 'dynamic',   args: { limit: '20' } },
  { group: '🇨🇳 国内',  label: 'Bilibili · 排行榜',           site: 'bilibili',     command: 'ranking',   args: { limit: '20' } },
  { group: '🇨🇳 国内',  label: '知乎 · 热榜',                 site: 'zhihu',        command: 'hot',       args: { limit: '20' } },
  { group: '🇨🇳 国内',  label: '微博 · 热搜',                 site: 'weibo',        command: 'hot',       args: {} },
  { group: '🇨🇳 国内',  label: '小红书 · 推荐流',             site: 'xiaohongshu',  command: 'feed',      args: { limit: '20' } },
  { group: '🇨🇳 国内',  label: '小红书 · 搜索',               site: 'xiaohongshu',  command: 'search',    args: { query: '', limit: '20' } },
  { group: '🇨🇳 国内',  label: 'V2EX · 热门',                 site: 'v2ex',         command: 'hot',       args: { limit: '20' } },
  { group: '🇨🇳 国内',  label: 'V2EX · 最新',                 site: 'v2ex',         command: 'latest',    args: { limit: '20' } },
  { group: '🇨🇳 国内',  label: '雪球 · 热股',                 site: 'xueqiu',       command: 'hot-stock', args: { limit: '20' } },
  { group: '🇨🇳 国内',  label: '雪球 · 热帖',                 site: 'xueqiu',       command: 'hot',       args: { limit: '20' } },
  // International
  { group: '🌍 Global', label: 'Twitter/X · trending',        site: 'twitter',      command: 'trending',  args: { limit: '20' } },
  { group: '🌍 Global', label: 'Twitter/X · timeline',        site: 'twitter',      command: 'timeline',  args: { limit: '20' } },
  { group: '🌍 Global', label: 'Twitter/X · bookmarks',       site: 'twitter',      command: 'bookmarks', args: { limit: '20' } },
  { group: '🌍 Global', label: 'Reddit · frontpage',          site: 'reddit',       command: 'frontpage', args: { limit: '20' } },
  { group: '🌍 Global', label: 'Reddit · hot',                site: 'reddit',       command: 'hot',       args: { limit: '20' } },
  { group: '🌍 Global', label: 'YouTube · search',            site: 'youtube',      command: 'search',    args: { query: 'technology', limit: '10' } },
  { group: '🌍 Global', label: 'LinkedIn · search',           site: 'linkedin',     command: 'search',    args: { query: 'AI engineer', limit: '20' } },
  { group: '🌍 Global', label: 'Yahoo Finance · quote',       site: 'yahoo-finance',command: 'quote',     args: { symbol: 'AAPL' } },
]

const PRESET_DEFAULT = OPENCLI_PRESETS[0]

function OpenCLIConfig({
  config,
  onChange,
}: {
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const { t } = useTranslation()
  const [args, setArgs] = useState<KVPair[]>(objToKv(config.args as Record<string, unknown>))

  const update = (patch: Partial<Record<string, unknown>>) => onChange({ ...config, ...patch })

  const updateArgs = (pairs: KVPair[]) => {
    setArgs(pairs)
    update({ args: kvToObj(pairs) })
  }

  const applyPreset = (label: string) => {
    const preset = OPENCLI_PRESETS.find((p) => p.label === label)
    if (!preset) return
    const newPairs = objToKv(preset.args)
    setArgs(newPairs)
    onChange({ site: preset.site, command: preset.command, args: preset.args, format: 'json' })
  }

  // Group presets for <optgroup>
  const groups = [...new Set(OPENCLI_PRESETS.map((p) => p.group))]

  const currentPreset = OPENCLI_PRESETS.find(
    (p) => p.site === config.site && p.command === config.command,
  )

  return (
    <div className="space-y-3">
      {/* Preset picker */}
      <Field label={t('channelConfig.quickPreset')} hint={t('channelConfig.quickPresetHint')}>
        <select
          className={input}
          value={currentPreset?.label ?? ''}
          onChange={(e) => applyPreset(e.target.value)}
        >
          <option value="">{t('channelConfig.customOption')}</option>
          {groups.map((g) => (
            <optgroup key={g} label={g}>
              {OPENCLI_PRESETS.filter((p) => p.group === g).map((p) => (
                <option key={p.label} value={p.label}>
                  {p.label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label={t('channelConfig.site')}>
          <TextInput
            value={(config.site as string) ?? ''}
            onChange={(v) => update({ site: v })}
            placeholder="hackernews"
            required
          />
        </Field>
        <Field label={t('channelConfig.command')}>
          <TextInput
            value={(config.command as string) ?? ''}
            onChange={(v) => update({ command: v })}
            placeholder="top"
            required
          />
        </Field>
      </div>
      <Field label={t('channelConfig.args')} hint={t('channelConfig.argsHint')}>
        <KVList pairs={args} onChange={updateArgs} keyPlaceholder="flag" valuePlaceholder="value" />
      </Field>
      <Field label={t('channelConfig.outputFormat')}>
        <SelectInput
          value={(config.format as string) ?? 'json'}
          onChange={(v) => update({ format: v })}
          options={[
            { value: 'json',  label: 'JSON' },
            { value: 'table', label: 'Table' },
            { value: 'yaml',  label: 'YAML' },
            { value: 'md',    label: 'Markdown' },
            { value: 'csv',   label: 'CSV' },
          ]}
        />
      </Field>
    </div>
  )
}

export { OPENCLI_PRESETS, PRESET_DEFAULT }

// ── Public component ──────────────────────────────────────────────────────────

export type ChannelType = 'rss' | 'api' | 'web_scraper' | 'cli' | 'opencli'

interface Props {
  channelType: ChannelType
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
}

export default function ChannelConfigForm({ channelType, config, onChange }: Props) {
  const mounted = useRef(false)
  // Reset config only when channel type changes after first render
  useEffect(() => {
    if (!mounted.current) { mounted.current = true; return }
    onChange({})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channelType])

  switch (channelType) {
    case 'rss':
      return <RSSConfig config={config} onChange={onChange} />
    case 'api':
      return <APIConfig config={config} onChange={onChange} />
    case 'web_scraper':
      return <WebScraperConfig config={config} onChange={onChange} />
    case 'cli':
      return <CLIConfig config={config} onChange={onChange} />
    case 'opencli':
      return <OpenCLIConfig config={config} onChange={onChange} />
  }
}
