import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getChromePool, listBrowserBindings, createBrowserBinding, deleteBrowserBinding } from '../api/endpoints'
import { PageLoader } from '../components/LoadingSpinner'
import ErrorAlert from '../components/ErrorAlert'
import Card from '../components/Card'
import PageHeader from '../components/PageHeader'
import { SITE_LABELS } from '../components/ChannelConfigForm'
import { Plus, Trash2, ExternalLink } from 'lucide-react'

const inputCls = 'w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500'
const labelCls = 'block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1'

/** Derive noVNC port from CDP URL hostname convention. */
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

function instanceLabel(cdpUrl: string): string {
  return cdpUrl.replace('http://', '').replace(':19222', '')
}

interface AddBindingFormProps {
  endpoints: string[]
  boundSites: Set<string>
  onAdd: (browser_endpoint: string, site: string, notes?: string) => void
  isPending: boolean
}

function AddBindingForm({ endpoints, boundSites, onAdd, isPending }: AddBindingFormProps) {
  const { t } = useTranslation()
  const [endpoint, setEndpoint] = useState(endpoints[0] ?? '')
  const [site, setSite] = useState('')
  const [notes, setNotes] = useState('')

  const handleSubmit = () => {
    if (!endpoint || !site.trim()) return
    onAdd(endpoint, site.trim(), notes.trim() || undefined)
    setSite('')
    setNotes('')
  }

  const allSites = Object.keys(SITE_LABELS)

  return (
    <div className="border border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-4 space-y-3">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{t('browsers.addBinding')}</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>{t('browsers.browser')}</label>
          <select className={inputCls} value={endpoint} onChange={(e) => setEndpoint(e.target.value)}>
            {endpoints.map((ep) => (
              <option key={ep} value={ep}>{instanceLabel(ep)}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>{t('browsers.site')}</label>
          <input
            className={inputCls}
            list="site-options"
            value={site}
            onChange={(e) => setSite(e.target.value)}
            placeholder={t('browsers.sitePlaceholder')}
          />
          <datalist id="site-options">
            {allSites.filter((s) => !boundSites.has(s)).map((s) => (
              <option key={s} value={s}>{SITE_LABELS[s]}</option>
            ))}
          </datalist>
        </div>
      </div>
      <div>
        <label className={labelCls}>{t('browsers.notes')} ({t('common.optional')})</label>
        <input
          className={inputCls}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={t('browsers.notesPlaceholder')}
        />
      </div>
      <button
        onClick={handleSubmit}
        disabled={isPending || !endpoint || !site.trim()}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
      >
        <Plus size={14} />
        {isPending ? t('common.loading') : t('browsers.bind')}
      </button>
    </div>
  )
}

export default function BrowsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [error422, setError422] = useState<string | null>(null)

  const { data: poolData, isLoading: poolLoading, error: poolError, refetch: refetchPool } = useQuery({
    queryKey: ['chrome-pool'],
    queryFn: getChromePool,
    refetchInterval: 10_000,
  })

  const { data: bindingsData, isLoading: bindingsLoading } = useQuery({
    queryKey: ['browser-bindings'],
    queryFn: listBrowserBindings,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['browser-bindings'] })
    setError422(null)
  }

  const addMutation = useMutation({
    mutationFn: createBrowserBinding,
    onSuccess: invalidate,
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError422(msg ?? t('common.error'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteBrowserBinding,
    onSuccess: invalidate,
  })

  if (poolLoading || bindingsLoading) return <PageLoader />
  if (poolError) return <ErrorAlert error={poolError as Error} onRetry={refetchPool} />

  const endpoints = poolData?.endpoints ?? []
  const bindings = bindingsData?.data ?? []

  // Group bindings by browser_endpoint
  const bindingsByEndpoint: Record<string, typeof bindings> = {}
  for (const ep of endpoints) {
    bindingsByEndpoint[ep.url] = []
  }
  for (const b of bindings) {
    if (!bindingsByEndpoint[b.browser_endpoint]) {
      bindingsByEndpoint[b.browser_endpoint] = []
    }
    bindingsByEndpoint[b.browser_endpoint].push(b)
  }

  // Unbound bindings (endpoint no longer in pool)
  const orphaned = bindings.filter((b) => !endpoints.find((e) => e.url === b.browser_endpoint))

  const boundSites = new Set(bindings.map((b) => b.site))
  const allEndpointUrls = endpoints.map((e) => e.url)

  return (
    <div>
      <PageHeader title={t('browsers.title')} description={t('browsers.description')} />

      {error422 && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-600">
          {error422}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {endpoints.map((ep) => {
          const novncPort = ep.novnc_port ?? chromeNovncPort(ep.url)
          const novncUrl = `http://${window.location.hostname}:${novncPort}`
          const label = instanceLabel(ep.url)
          const epBindings = bindingsByEndpoint[ep.url] ?? []

          return (
            <Card key={ep.url}>
              {/* Instance header */}
              <div className="flex items-center gap-2 mb-3">
                <span className={`w-2 h-2 rounded-full ${ep.available ? 'bg-green-500' : 'bg-red-400'}`} />
                <span className="font-semibold text-sm">{label}</span>
                <a
                  href={novncUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-auto flex items-center gap-1 text-xs text-blue-500 hover:underline font-mono"
                >
                  {window.location.hostname}:{novncPort}
                  <ExternalLink size={11} />
                </a>
              </div>

              {/* Bound sites */}
              <div className="space-y-1.5 mb-3 min-h-[2rem]">
                {epBindings.length === 0 ? (
                  <p className="text-xs text-gray-400">{t('browsers.noBindings')}</p>
                ) : epBindings.map((b) => (
                  <div key={b.id} className="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 rounded px-2 py-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-medium">{SITE_LABELS[b.site] ?? b.site}</span>
                      <span className="text-xs text-gray-400 font-mono">({b.site})</span>
                    </div>
                    <button
                      onClick={() => deleteMutation.mutate(b.id)}
                      disabled={deleteMutation.isPending}
                      className="text-gray-400 hover:text-red-500 transition-colors p-0.5 rounded"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>

              {/* Quick add for this instance */}
              <QuickAddSite
                browserEndpoint={ep.url}
                allEndpoints={allEndpointUrls}
                boundSites={boundSites}
                onAdd={(site, notes) => addMutation.mutate({ browser_endpoint: ep.url, site, notes })}
                isPending={addMutation.isPending}
              />
            </Card>
          )
        })}
      </div>

      {/* Orphaned bindings */}
      {orphaned.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">{t('browsers.orphaned')}</h3>
          <Card>
            <div className="space-y-1.5">
              {orphaned.map((b) => (
                <div key={b.id} className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">
                    {SITE_LABELS[b.site] ?? b.site} → <span className="font-mono text-xs">{b.browser_endpoint}</span>
                  </span>
                  <button
                    onClick={() => deleteMutation.mutate(b.id)}
                    className="text-gray-400 hover:text-red-500 p-1"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Global add binding form */}
      <div className="mt-6">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('browsers.addBinding')}</h3>
        <Card>
          <AddBindingForm
            endpoints={allEndpointUrls}
            boundSites={boundSites}
            onAdd={(browser_endpoint, site, notes) => addMutation.mutate({ browser_endpoint, site, notes })}
            isPending={addMutation.isPending}
          />
        </Card>
      </div>
    </div>
  )
}

interface QuickAddSiteProps {
  browserEndpoint: string
  allEndpoints: string[]
  boundSites: Set<string>
  onAdd: (site: string, notes?: string) => void
  isPending: boolean
}

function QuickAddSite({ boundSites, onAdd, isPending }: QuickAddSiteProps) {
  const { t } = useTranslation()
  const [site, setSite] = useState('')

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && site.trim()) {
      onAdd(site.trim())
      setSite('')
    }
  }

  const allSites = Object.keys(SITE_LABELS)

  return (
    <div className="flex items-center gap-2">
      <input
        className="flex-1 px-2 py-1 text-xs border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        list="quick-site-options"
        value={site}
        onChange={(e) => setSite(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={t('browsers.sitePlaceholder')}
      />
      <datalist id="quick-site-options">
        {allSites.filter((s) => !boundSites.has(s)).map((s) => (
          <option key={s} value={s}>{SITE_LABELS[s]}</option>
        ))}
      </datalist>
      <button
        onClick={() => { if (site.trim()) { onAdd(site.trim()); setSite('') } }}
        disabled={isPending || !site.trim()}
        className="p-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
      >
        <Plus size={13} />
      </button>
    </div>
  )
}
