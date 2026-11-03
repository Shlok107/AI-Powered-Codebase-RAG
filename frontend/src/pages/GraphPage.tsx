import { Link } from 'react-router-dom'
import { Card } from '../components'
import { GitBranch, ArrowRight, Info } from 'lucide-react'

export function GraphPage() {
  return <div className="space-y-7 animate-in">
    <div><p className="text-xs uppercase tracking-[.14em] text-accent mb-2">Explore</p><h1 className="text-2xl font-semibold tracking-tight text-text-primary">Dependency graph</h1><p className="text-sm text-text-secondary mt-1">Inspect relationships between modules and files.</p></div>
    <Card padding="none" className="overflow-hidden">
      <div className="grid lg:grid-cols-[1fr_280px] min-h-[420px]">
        <div className="relative flex flex-col items-center justify-center p-8 text-center bg-background/40">
          <div className="absolute inset-0 opacity-[.16]" style={{ backgroundImage: 'radial-gradient(#8178C8 1px, transparent 1px)', backgroundSize: '22px 22px' }} aria-hidden="true" />
          <div className="relative h-12 w-12 rounded-lg border border-surface-border bg-surface flex items-center justify-center"><GitBranch className="h-5 w-5 text-text-muted" /></div>
          <h2 className="relative mt-4 text-base font-semibold text-text-primary">Graph data is not available yet</h2>
          <p className="relative mt-2 max-w-md text-sm leading-relaxed text-text-secondary">The current service does not extract or return dependency relationships. No graph is shown until real relationship data is available.</p>
          <Link className="relative mt-5 btn-secondary" to="/repositories">Browse repositories<ArrowRight className="h-4 w-4" /></Link>
        </div>
        <aside className="border-t lg:border-t-0 lg:border-l border-surface-border p-5">
          <p className="text-xs uppercase tracking-[.14em] text-text-muted">About this view</p>
          <div className="mt-4 flex gap-3"><Info className="h-4 w-4 text-accent shrink-0 mt-0.5" /><p className="text-sm leading-relaxed text-text-secondary">Dependency parsing and graph visualization are not implemented in the current frontend and API.</p></div>
          <div className="mt-6 border-t border-surface-border pt-4"><p className="text-xs text-text-muted">STATUS</p><p className="mt-1 text-sm text-text-primary">Unavailable</p></div>
        </aside>
      </div>
    </Card>
  </div>
}
