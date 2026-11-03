import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Badge, Button } from '../components'
import { cn } from '../utils/cn'
import { Database, MessageSquare, FileCode, Shield, RefreshCw, Info, HelpCircle } from 'lucide-react'
import { formatRelativeTime } from '../utils/format'

interface HealthStatus {
  status: string
  database: string
  llm_provider: string
  embedding_provider: string
  version?: string
  timestamp?: string
}

export function SettingsPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => { void fetchHealth() }, [])

  async function fetchHealth() {
    setLoading(true)
    setError('')
    try { setHealth(await api.health()) }
    catch { setHealth(null); setError('System status could not be reached. Check the API connection and try again.') }
    finally { setLoading(false) }
  }

  const statusBadge = (value: string) => {
    const healthy = ['connected', 'configured', 'healthy'].includes(value)
    return <Badge variant={healthy ? 'success' : value === 'degraded' ? 'warning' : 'default'}>{value}</Badge>
  }
  const rows = health ? [
    { title: 'Application', detail: 'API service health', value: health.status, icon: Shield },
    { title: 'Database', detail: 'Repository and index storage', value: health.database, icon: Database },
    { title: 'Language model', detail: 'Code question answering provider', value: health.llm_provider, icon: MessageSquare },
    { title: 'Embeddings', detail: 'Semantic retrieval provider', value: health.embedding_provider, icon: FileCode },
  ] : []

  return <div className="max-w-6xl space-y-5 animate-in">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-[10px] uppercase tracking-[.15em] text-text-muted mb-1">Workspace / System</p><h1 className="text-xl font-semibold tracking-tight text-text-primary">Settings</h1><p className="text-sm text-text-secondary mt-1">Inspect connected services and read-only runtime information.</p></div>
      <Button size="sm" variant="secondary" onClick={fetchHealth} disabled={loading}><RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />Refresh status</Button>
    </div>

    <div className="grid gap-7 lg:grid-cols-[160px_minmax(0,1fr)]">
      <aside className="hidden lg:block">
        <nav aria-label="Settings sections" className="sticky top-16 space-y-1 border-l border-surface-border pl-3">
          <a className="block py-1.5 text-xs text-text-secondary hover:text-text-primary" href="#service-health">Service health</a>
          <a className="block py-1.5 text-xs text-text-secondary hover:text-text-primary" href="#configuration">Configuration</a>
          <a className="block py-1.5 text-xs text-text-secondary hover:text-text-primary" href="#about">About</a>
        </nav>
      </aside>
      <div className="min-w-0 space-y-7">
    <section id="service-health" className="scroll-mt-16">
      <div className="mb-3"><h2 className="text-sm font-semibold text-text-primary">Service health</h2><p className="text-xs text-text-muted mt-1">Live status reported by the connected API.</p></div>
      <div className="border-y border-surface-border">
        {loading ? <div className="py-3 space-y-2" aria-label="Loading system status">{[1,2,3,4].map((i) => <div key={i} className="h-11 bg-background-secondary animate-pulse" />)}</div> : error ? <div className="py-5" role="alert"><p className="text-sm text-red-300">{error}</p><Button variant="secondary" size="sm" className="mt-3" onClick={fetchHealth}>Retry</Button></div> : <>
          <div className="divide-y divide-surface-border">{rows.map(({ title, detail, value, icon: Icon }) => <div key={title} className="flex items-center gap-3 py-3">
            <div className="h-7 w-7 rounded bg-background-tertiary flex items-center justify-center"><Icon className="h-3.5 w-3.5 text-text-secondary" /></div>
            <div className="min-w-0 flex-1"><p className="text-xs font-medium text-text-primary">{title}</p><p className="text-[11px] text-text-muted mt-0.5">{detail}</p></div>
            {statusBadge(value)}
          </div>)}</div>
          <div className="border-t border-surface-border py-2.5 flex flex-wrap items-center justify-between gap-2 text-[10px]">{health?.version && <span className="text-text-muted">API <span className="ml-1 font-mono text-text-secondary">{health.version}</span></span>}{health?.timestamp && <span className="text-text-muted">Reported {formatRelativeTime(health.timestamp)}</span>}</div>
        </>}
      </div>
    </section>

    <section id="configuration" className="scroll-mt-16">
      <div className="mb-3"><h2 className="text-sm font-semibold text-text-primary">Configuration</h2><p className="text-xs text-text-muted mt-1">Runtime configuration is managed by the service operator.</p></div>
      <div className="flex gap-3 border-y border-surface-border py-4"><HelpCircle className="h-4 w-4 mt-0.5 text-accent shrink-0" /><div><p className="text-sm text-text-primary">Provider and indexing settings are read-only here.</p><p className="text-sm text-text-secondary mt-1 leading-relaxed">This workspace does not expose a configuration update API. Provider credentials and service limits are kept outside the browser and are not displayed in this interface.</p></div></div>
    </section>

    <section id="about" className="scroll-mt-16">
      <div className="mb-3"><h2 className="text-sm font-semibold text-text-primary">About Codebase RAG</h2></div>
      <div className="border-y border-surface-border py-4"><div className="flex gap-2"><Info className="h-4 w-4 text-accent shrink-0" /><p className="text-sm text-text-secondary leading-relaxed">Codebase RAG combines repository ingestion, code-aware indexing, semantic retrieval, grounded code questions, and deterministic security checks.</p></div><div className="mt-3 pt-3 border-t border-surface-border flex flex-wrap gap-x-8 gap-y-2 text-xs"><span className="text-text-muted">Version <strong className="ml-1 font-mono text-text-secondary">0.1.0 MVP</strong></span><span className="text-text-muted">Security findings are advisory and should be reviewed in context.</span></div></div>
    </section>
      </div>
    </div>
  </div>
}
