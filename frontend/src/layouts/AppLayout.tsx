import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '../components/Sidebar'
import { NetworkBackground } from '../components/NetworkBackground'
import { Menu, ChevronRight } from 'lucide-react'
import { useState } from 'react'

export function AppLayout() {
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const section = getPageTitle(location.pathname)

  return <div className="app-shell flex h-[100dvh] w-full min-w-0 overflow-hidden bg-background">
    <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <header className="relative z-30 h-12 shrink-0 border-b border-surface-border bg-background-secondary/95">
        <div className="h-full px-4 sm:px-6 flex items-center gap-3">
          <button onClick={() => setMobileOpen(true)} className="lg:hidden inline-flex p-2 -ml-2 rounded-md text-text-secondary hover:text-text-primary hover:bg-surface" aria-label="Open navigation"><Menu className="h-5 w-5" /></button>
          <div className="flex items-center gap-2 text-sm min-w-0">
            <span className="hidden sm:inline text-text-muted">Workspace</span><ChevronRight className="hidden sm:block h-3 w-3 text-text-muted" />
            <span className="font-medium text-text-primary truncate">{section}</span>
          </div>
          <span className="ml-auto hidden sm:inline text-[11px] text-text-muted font-mono">CODEBASE RAG</span>
        </div>
      </header>
      <div className="relative isolate flex min-h-0 min-w-0 flex-1 bg-[#050505]">
        <NetworkBackground />
        <main className="relative z-10 min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto bg-transparent p-3 sm:p-4 lg:p-5"><div className="w-full min-w-0"><Outlet /></div></main>
      </div>
    </div>
  </div>
}

function getPageTitle(pathname: string): string {
  if (pathname.startsWith('/repositories/')) return 'Repository detail'
  if (pathname.startsWith('/chat/')) return 'Ask Codebase'
  if (pathname.startsWith('/security/')) return 'Security analysis'
  const titles: Record<string, string> = { '/': 'Overview', '/repositories': 'Repositories', '/chat': 'Ask Codebase', '/security': 'Security analysis', '/graph': 'Dependency graph', '/settings': 'Settings' }
  return titles[pathname] || 'Codebase RAG'
}
