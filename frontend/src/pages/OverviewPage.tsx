import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Repository } from '../types'
import { Badge, Button } from '../components'
import { formatRelativeTime, getErrorMessage, getLanguageLabel } from '../utils/format'
import { cn } from '../utils/cn'
import { Database, FileCode, Loader2, CheckCircle, XCircle, Plus, Upload, MessageSquare, Shield, RefreshCw, ArrowUpRight, Settings } from 'lucide-react'

interface HealthStatus { status: string; database: string; llm_provider: string; embedding_provider: string }

export function OverviewPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [healthRes, reposRes] = await Promise.all([api.health(), api.listRepositories({ limit: 100 })])
      setHealth(healthRes)
      setRepositories([...reposRes.repositories].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()))
      setTotal(reposRes.total)
    } catch (err) {
      setError(getErrorMessage(err, 'Could not load workspace data. Check the API connection and try again.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchData() }, [fetchData])

  const indexed = repositories.filter((repo) => repo.status === 'indexed').length
  const processingOnly = repositories.filter((repo) => repo.status === 'processing').length
  const pending = repositories.filter((repo) => repo.status === 'pending').length
  const failed = repositories.filter((repo) => repo.status === 'failed').length
  const processing = processingOnly + pending
  const loadedCount = repositories.length
  const filesLoaded = repositories.reduce((sum, repo) => sum + repo.file_count, 0)
  const chunksLoaded = repositories.reduce((sum, repo) => sum + repo.chunk_count, 0)
  const percent = (count: number) => loadedCount === 0 ? 0 : (count / loadedCount) * 100

  const healthItems = health ? [
    { label: 'API service', value: health.status, ok: health.status === 'healthy', icon: Shield },
    { label: 'Database', value: health.database, ok: health.database === 'connected', icon: Database },
    { label: 'Code Q&A', value: health.llm_provider, ok: health.llm_provider === 'configured', icon: MessageSquare },
    { label: 'Embeddings', value: health.embedding_provider, ok: health.embedding_provider === 'configured', icon: FileCode },
  ] : []

  return <div className="space-y-5 animate-in">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="mb-1 text-[10px] uppercase tracking-[.18em] text-accent-light">Engineering / Command center</p><h1 className="text-xl font-semibold tracking-tight text-text-primary">Overview</h1><p className="mt-1 text-xs text-text-secondary">Repository inventory, indexing activity, and connected service health.</p></div>
      <Link to="/repositories" className="btn-primary"><Plus className="h-4 w-4" />Add repository</Link>
    </header>

    {error && <div className="flex items-center justify-between gap-3 border border-status-danger/25 bg-status-danger/5 px-3 py-2" role="alert"><p className="text-xs text-status-danger">{error}</p><Button variant="secondary" size="sm" onClick={fetchData}><RefreshCw className="h-3.5 w-3.5" />Retry</Button></div>}

    <section className="overflow-hidden border border-surface-border bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-border bg-background-tertiary/70 px-3 py-2"><h2 className="text-[10px] font-semibold uppercase tracking-[.14em] text-text-secondary">Repository inventory</h2><span className="text-[10px] text-text-muted">Total: API · status counts: {loadedCount} loaded</span></div>
      <div className="grid grid-cols-2 divide-x divide-y divide-surface-border lg:grid-cols-4 lg:divide-y-0">
        <Stat label="Repositories" value={total} icon={<Database className="h-3.5 w-3.5" />} tone="text-accent-light" />
        <Stat label="Indexed" value={indexed} icon={<CheckCircle className="h-3.5 w-3.5" />} tone="text-status-success" />
        <Stat label="In progress" value={processing} icon={<Loader2 className="h-3.5 w-3.5" />} tone="text-status-warning" />
        <Stat label="Failed" value={failed} icon={<XCircle className="h-3.5 w-3.5" />} tone={failed ? 'text-status-danger' : 'text-text-muted'} />
      </div>
    </section>

    <section className="border-y border-surface-border bg-background-secondary/70">
      <div className="flex items-center justify-between gap-3 border-b border-surface-border px-3 py-2"><div><h2 className="text-[10px] font-semibold uppercase tracking-[.14em] text-text-secondary">Connected services</h2><p className="mt-0.5 text-[10px] text-text-muted">Health reported by the API.</p></div><Button variant="ghost" size="sm" onClick={fetchData} disabled={loading}><RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} /><span className="hidden sm:inline">Refresh</span></Button></div>
      {loading && !health ? <div className="grid grid-cols-2 gap-px bg-surface-border lg:grid-cols-4">{[1, 2, 3, 4].map((item) => <div key={item} className="h-12 animate-pulse bg-background-secondary" />)}</div> : healthItems.length ? <div className="grid grid-cols-2 divide-x divide-y divide-surface-border lg:grid-cols-4 lg:divide-y-0">{healthItems.map(({ label, value, ok, icon: Icon }) => <div key={label} className="flex min-w-0 items-center gap-2.5 px-3 py-2.5"><Icon className={cn('h-3.5 w-3.5 shrink-0', ok ? 'text-status-success' : 'text-status-warning')} /><div className="min-w-0"><p className="text-[10px] text-text-muted">{label}</p><p className="truncate text-xs font-medium capitalize text-text-primary">{value}</p></div><span className={cn('ml-auto h-1.5 w-1.5 shrink-0 rounded-full', ok ? 'bg-status-success' : 'bg-status-warning')} /></div>)}</div> : <p className="px-3 py-3 text-xs text-text-muted">Service health unavailable.</p>}
    </section>

    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
      <section className="min-w-0">
        <div className="mb-2 flex items-center justify-between"><div><h2 className="text-sm font-semibold text-text-primary">Recent repositories</h2><p className="mt-0.5 text-[10px] text-text-muted">Latest updates from the loaded repository set.</p></div><Link to="/repositories" className="inline-flex items-center gap-1 text-[11px] text-accent-light hover:text-white">View all<ArrowUpRight className="h-3 w-3" /></Link></div>
        <div className="overflow-hidden border-y border-surface-border bg-surface">
          {loading && repositories.length === 0 ? <div className="p-8 text-center text-xs text-text-muted" role="status"><Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin text-accent" />Loading repositories…</div> : repositories.length === 0 ? <div className="px-5 py-10 text-center"><div className="mx-auto flex h-9 w-9 items-center justify-center rounded border border-surface-border bg-background-tertiary"><Database className="h-4 w-4 text-accent-light" /></div><h3 className="mt-3 text-sm font-semibold text-text-primary">No repositories yet</h3><p className="mt-1 text-xs text-text-secondary">Upload a ZIP archive to start indexing and reviewing code.</p><Link to="/repositories" className="btn-secondary mt-3 text-xs"><Upload className="h-3.5 w-3.5" />Upload repository</Link></div> : <div className="divide-y divide-surface-border">{repositories.slice(0, 7).map((repo) => <Link key={repo.id} to={`/repositories/${repo.id}`} className="flex min-w-0 items-center gap-2.5 px-3 py-2.5 transition-colors hover:bg-surface-hover/60"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-background-tertiary"><FileCode className="h-3.5 w-3.5 text-accent-light" /></span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium text-text-primary">{repo.display_name}</span><span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[10px] text-text-muted"><Badge variant={repo.status as any}>{repo.status}</Badge>{repo.detected_languages.slice(0, 2).map((language) => <span key={language}>{getLanguageLabel(language)}</span>)}<span>{repo.file_count.toLocaleString()} files</span><span>{repo.chunk_count.toLocaleString()} chunks</span></span></span><span className="shrink-0 text-right text-[10px] text-text-muted">{formatRelativeTime(repo.updated_at)}</span></Link>)}</div>}
        </div>
      </section>

      <aside className="space-y-5">
        <section className="border border-surface-border bg-surface">
          <div className="border-b border-surface-border bg-background-tertiary/70 px-3 py-2"><h2 className="text-[10px] font-semibold uppercase tracking-[.14em] text-text-secondary">Indexing analytics</h2><p className="mt-0.5 text-[10px] text-text-muted">{loadedCount} loaded repositories</p></div>
          <div className="p-3">
            {loadedCount > 0 ? <>
              <div className="flex h-2 overflow-hidden rounded-sm bg-background-tertiary" role="img" aria-label={`${indexed} indexed, ${processingOnly} processing, ${pending} pending, ${failed} failed`}>
                {indexed > 0 && <span className="bg-status-success" style={{ width: `${percent(indexed)}%` }} />}
                {processingOnly > 0 && <span className="bg-status-cyan" style={{ width: `${percent(processingOnly)}%` }} />}
                {pending > 0 && <span className="bg-status-warning" style={{ width: `${percent(pending)}%` }} />}
                {failed > 0 && <span className="bg-status-danger" style={{ width: `${percent(failed)}%` }} />}
              </div>
              <div className="mt-3 space-y-2">{[
                { label: 'Indexed', count: indexed, color: 'bg-status-success' },
                { label: 'Processing', count: processingOnly, color: 'bg-status-cyan' },
                { label: 'Pending', count: pending, color: 'bg-status-warning' },
                { label: 'Failed', count: failed, color: 'bg-status-danger' },
              ].map((item) => <div key={item.label} className="flex items-center gap-2 text-[11px]"><span className={cn('h-1.5 w-1.5 rounded-full', item.color)} /><span className="flex-1 text-text-secondary">{item.label}</span><span className="font-mono tabular-nums text-text-primary">{item.count}</span></div>)}</div>
              <div className="mt-3 grid grid-cols-2 border-t border-surface-border pt-3"><div><p className="text-[10px] text-text-muted">Files in loaded set</p><p className="mt-0.5 font-mono text-sm tabular-nums text-text-primary">{filesLoaded.toLocaleString()}</p></div><div><p className="text-[10px] text-text-muted">Code chunks</p><p className="mt-0.5 font-mono text-sm tabular-nums text-text-primary">{chunksLoaded.toLocaleString()}</p></div></div>
            </> : <p className="py-3 text-xs text-text-muted">Indexing data will appear when repositories are available.</p>}
            {total > loadedCount && <p className="mt-3 border-t border-surface-border pt-2 text-[10px] leading-relaxed text-text-muted">Distribution and file totals reflect the {loadedCount} repositories loaded here; {total.toLocaleString()} exist in total.</p>}
          </div>
        </section>

        <section className="border border-accent/25 bg-accent/5">
          <div className="flex items-start gap-2.5 p-3"><Shield className="mt-0.5 h-4 w-4 shrink-0 text-accent-light" /><div><h2 className="text-xs font-semibold text-text-primary">Security analysis</h2><p className="mt-1 text-[11px] leading-relaxed text-text-secondary">Findings and scan results are available within each repository.</p><Link to="/security" className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-accent-light hover:text-white">Choose a repository<ArrowUpRight className="h-3 w-3" /></Link></div></div>
        </section>

        <section className="border border-surface-border bg-surface">
          <div className="border-b border-surface-border bg-background-tertiary/70 px-3 py-2"><h2 className="text-[10px] font-semibold uppercase tracking-[.14em] text-text-secondary">Workspace shortcuts</h2></div>
          <div className="divide-y divide-surface-border">
            <Shortcut to="/repositories" icon={<Database className="h-3.5 w-3.5" />} title="Repositories" detail="Upload and inspect" />
            <Shortcut to="/chat" icon={<MessageSquare className="h-3.5 w-3.5" />} title="Ask Codebase" detail="Investigate indexed code" />
            <Shortcut to="/settings" icon={<Settings className="h-3.5 w-3.5" />} title="Service status" detail="Review connected services" />
          </div>
        </section>
      </aside>
    </div>
  </div>
}

function Stat({ label, value, icon, tone = 'text-text-secondary' }: { label: string; value: number; icon: ReactNode; tone?: string }) {
  return <div className="px-3 py-3 sm:px-4"><div className={cn('flex items-center gap-1.5', tone)}>{icon}<span className="text-[10px] text-text-muted">{label}</span></div><p className="mt-1.5 text-xl font-semibold tracking-tight tabular-nums text-text-primary">{value.toLocaleString()}</p></div>
}

function Shortcut({ to, icon, title, detail }: { to: string; icon: ReactNode; title: string; detail: string }) {
  return <Link to={to} className="flex items-center gap-2.5 px-3 py-2 transition-colors hover:bg-surface-hover/50"><div className="flex h-6 w-6 items-center justify-center rounded bg-background-tertiary text-accent-light">{icon}</div><div className="min-w-0 flex-1"><p className="text-xs font-medium text-text-primary">{title}</p><p className="mt-0.5 text-[10px] text-text-muted">{detail}</p></div><ArrowUpRight className="h-3 w-3 text-text-muted" /></Link>
}
