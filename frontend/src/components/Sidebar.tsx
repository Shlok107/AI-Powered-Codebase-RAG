import { NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { cn } from '../utils/cn'
import { LayoutDashboard, Database, MessageSquare, Shield, GitBranch, Settings, ChevronLeft, ChevronRight, ScanLine, X } from 'lucide-react'

const navigation = [
  { name: 'Overview', href: '/', icon: LayoutDashboard },
  { name: 'Repositories', href: '/repositories', icon: Database },
  { name: 'Ask Codebase', href: '/chat', icon: MessageSquare },
  { name: 'Security', href: '/security', icon: Shield },
  { name: 'Dependency graph', href: '/graph', icon: GitBranch },
  { name: 'Settings', href: '/settings', icon: Settings },
]

interface SidebarProps { mobileOpen?: boolean; onMobileClose?: () => void }

export function Sidebar({ mobileOpen = false, onMobileClose }: SidebarProps) {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <>
      {mobileOpen && <button aria-label="Close navigation" onClick={onMobileClose} className="fixed inset-0 z-40 bg-black/60 lg:hidden" />}
      <aside className={cn(
        'fixed left-0 top-0 z-50 h-[100dvh] shrink-0 bg-sidebar border-r border-white/10 flex flex-col transition-[width,transform] duration-200 lg:static lg:z-auto lg:h-full',
        collapsed ? 'w-14' : 'w-56',
        mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      )} aria-label="Main navigation">
        <div className="flex items-center justify-between h-14 px-3.5 border-b border-surface-border">
          {!collapsed && <NavLink to="/" onClick={onMobileClose} className="flex items-center gap-3" aria-label="Codebase RAG Home">
            <div className="w-8 h-8 rounded-md bg-sidebar-secondary border border-sidebar-accent/30 flex items-center justify-center"><ScanLine className="h-4 w-4 text-sidebar-accent" /></div>
            <span className="font-semibold tracking-tight text-text-primary">Codebase <span className="text-text-secondary font-normal">RAG</span></span>
          </NavLink>}
          <button onClick={() => setCollapsed((value) => !value)} className={cn('hidden lg:inline-flex p-1.5 rounded-md text-text-secondary hover:text-text-primary hover:bg-surface transition-colors', collapsed && 'mx-auto')} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed}>
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
          <button onClick={onMobileClose} className="lg:hidden p-1.5 rounded-md text-text-secondary hover:bg-surface" aria-label="Close navigation"><X className="h-4 w-4" /></button>
        </div>
        {!collapsed && <div className="px-4 pt-5 pb-2 text-[10px] uppercase tracking-[.16em] text-text-muted">Workspace</div>}
        <nav className="min-h-0 flex-1 px-2.5 py-1 space-y-0.5 overflow-y-auto" aria-label="Navigation">
          {navigation.map((item) => {
            const active = location.pathname === item.href || (item.href !== '/' && location.pathname.startsWith(item.href))
            return <NavLink key={item.name} to={item.href} onClick={onMobileClose} className={cn('sidebar-link', active && 'sidebar-link-active', collapsed && 'justify-center px-2')} title={collapsed ? item.name : undefined} aria-current={active ? 'page' : undefined}>
              <item.icon className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
              {!collapsed && <span>{item.name}</span>}
            </NavLink>
          })}
        </nav>
        <div className={cn('mt-auto shrink-0 border-t border-white/10', collapsed ? 'px-2 py-3 text-center' : 'px-4 py-3')}>
          {collapsed ? <span title="Codebase Intelligence" className="text-[9px] font-semibold tracking-wider text-sidebar-accent">CI</span> : <p className="text-[10px] font-medium uppercase tracking-[.14em] text-sidebar-accent">Codebase Intelligence</p>}
        </div>
      </aside>
    </>
  )
}
