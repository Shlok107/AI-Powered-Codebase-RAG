import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '../utils/cn'
import {
  LayoutDashboard,
  Database,
  MessageSquare,
  Shield,
  GitBranch,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { useState } from 'react'

const navigation = [
  { name: 'Overview', href: '/', icon: LayoutDashboard },
  { name: 'Repositories', href: '/repositories', icon: Database },
  { name: 'Ask Codebase', href: '/chat', icon: MessageSquare },
  { name: 'Security', href: '/security', icon: Shield },
  { name: 'Graph', href: '/graph', icon: GitBranch },
  { name: 'Settings', href: '/settings', icon: Settings },
]

interface SidebarProps {
  onToggle?: () => void
}

export function Sidebar({ onToggle }: SidebarProps) {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen bg-background border-r border-surface-border transition-all duration-300 flex flex-col',
        collapsed ? 'w-16' : 'w-64'
      )}
      aria-label="Main navigation"
    >
      <div className="flex items-center justify-between h-16 px-4 border-b border-surface-border">
        {!collapsed && (
          <NavLink to="/" className="flex items-center gap-2" aria-label="Codebase RAG Home">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
              <Shield className="h-5 w-5 text-white" />
            </div>
            <span className="font-semibold text-text-primary">Codebase RAG</span>
          </NavLink>
        )}
        <button
          onClick={() => {
            setCollapsed(!collapsed)
            onToggle?.()
          }}
          className={cn(
            'p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface transition-colors',
            collapsed && 'ml-auto'
          )}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
        >
          {collapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
        </button>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" aria-label="Navigation">
        {navigation.map((item) => {
          const isActive = location.pathname === item.href || (item.href !== '/' && location.pathname.startsWith(item.href))
          return (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive: active }) => cn(
                'sidebar-link',
                active && 'sidebar-link-active',
                collapsed && 'justify-center px-2'
              )}
              title={collapsed ? item.name : undefined}
              aria-current={isActive ? 'page' : undefined}
            >
              <item.icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
              {!collapsed && <span>{item.name}</span>}
            </NavLink>
          )
        })}
      </nav>

      <div className="p-3 border-t border-surface-border">
        {!collapsed && (
          <div className="text-xs text-text-muted px-2">
            <p className="font-medium mb-1">Quick Actions</p>
            <p>Press <kbd className="px-1.5 py-0.5 bg-surface-border rounded">K</kbd> for command palette</p>
          </div>
        )}
      </div>
    </aside>
  )
}