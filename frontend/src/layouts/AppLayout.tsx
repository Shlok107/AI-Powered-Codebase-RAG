import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '../components/Sidebar'
import { cn } from '../utils/cn'
import { useState } from 'react'

export function AppLayout() {
  const location = useLocation()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="min-h-screen bg-background flex">
      <Sidebar onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />
      <div
        className={cn(
          'flex-1 flex flex-col min-w-0 transition-all duration-300',
          sidebarCollapsed ? 'lg:ml-16' : 'lg:ml-64'
        )}
      >
        <header className="sticky top-0 z-30 h-16 bg-background/80 backdrop-blur-md border-b border-surface-border">
          <div className="h-full px-6 flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-text-primary">
                {getPageTitle(location.pathname)}
              </h1>
              <p className="text-sm text-text-secondary mt-0.5">
                {getPageDescription(location.pathname)}
              </p>
            </div>
            <div className="flex items-center gap-4">
              {/* Repository selector would go here */}
            </div>
          </div>
        </header>

        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function getPageTitle(pathname: string): string {
  const titles: Record<string, string> = {
    '/': 'Overview',
    '/repositories': 'Repositories',
    '/chat': 'Ask Codebase',
    '/security': 'Security Findings',
    '/graph': 'Dependency Graph',
    '/settings': 'Settings',
  }

  // Check for dynamic routes
  if (pathname.startsWith('/repositories/')) return 'Repository Details'
  if (pathname.startsWith('/chat/')) return 'Conversation'

  return titles[pathname] || 'Codebase RAG'
}

function getPageDescription(pathname: string): string {
  const descriptions: Record<string, string> = {
    '/': 'Repository status, indexing progress, and recent activity',
    '/repositories': 'Manage and browse your code repositories',
    '/chat': 'Ask questions about your codebase with grounded answers',
    '/security': 'View and triage security findings across repositories',
    '/graph': 'Explore code dependencies and relationships',
    '/settings': 'Configure providers, integrations, and preferences',
  }

  if (pathname.startsWith('/repositories/')) return 'View repository details, files, and indexing status'
  if (pathname.startsWith('/chat/')) return 'Continue your conversation about this repository'

  return descriptions[pathname] || ''
}