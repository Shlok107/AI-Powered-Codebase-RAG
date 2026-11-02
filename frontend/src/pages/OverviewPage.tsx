import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Repository } from '../types'
import { Card, CardHeader, CardTitle, CardContent } from '../components'
import { formatRelativeTime } from '../utils/format'
import { cn } from '../utils/cn'
import {
  Database,
  FileCode,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
  Plus,
  Upload,
  MessageSquare,
  Shield,
  Settings,
} from 'lucide-react'
import { Badge } from '../components/Badge'

interface HealthStatus {
  status: string
  database: string
  llm_provider: string
  embedding_provider: string
  version?: string
  timestamp?: string
}

export function OverviewPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true)
        const [healthRes, reposRes] = await Promise.all([
          api.health(),
          api.listRepositories({ limit: 5 }),
        ])
        setHealth(healthRes)
        setRepositories(reposRes.repositories)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="space-y-6 animate-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Overview</h1>
            <p className="text-text-secondary mt-1">Repository status, indexing progress, and recent activity</p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} className="animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  const stats = {
    totalRepos: repositories.length,
    indexedRepos: repositories.filter((r) => r.status === 'indexed').length,
    processingRepos: repositories.filter((r) => r.status === 'processing').length,
    failedRepos: repositories.filter((r) => r.status === 'failed').length,
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'indexed': return <CheckCircle className="h-5 w-5 text-green-400" />
      case 'processing': return <Loader2 className="h-5 w-5 text-blue-400 animate-spin" />
      case 'failed': return <XCircle className="h-5 w-5 text-red-400" />
      default: return <AlertCircle className="h-5 w-5 text-yellow-400" />
    }
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Overview</h1>
          <p className="text-text-secondary mt-1">Repository status, indexing progress, and recent activity</p>
        </div>
        <Link to="/repositories" className="btn-primary">
          <Plus className="h-4 w-4" />
          Add Repository
        </Link>
      </div>

      {/* System Health */}
      <Card padding="md" className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            System Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="flex items-center gap-3 p-3 bg-surface-border/50 rounded-lg">
              <Database className={cn('h-5 w-5', health?.database === 'connected' ? 'text-green-400' : 'text-red-400')} />
              <div>
                <p className="text-sm font-medium text-text-primary">Database</p>
                <p className="text-xs text-text-secondary">
                  {health?.database === 'connected' ? 'Connected' : 'Disconnected'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-surface-border/50 rounded-lg">
              <MessageSquare className={cn('h-5 w-5', health?.llm_provider === 'configured' ? 'text-green-400' : 'text-yellow-400')} />
              <div>
                <p className="text-sm font-medium text-text-primary">LLM Provider</p>
                <p className="text-xs text-text-secondary">
                  {health?.llm_provider === 'configured' ? 'Configured' : 'Not configured'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-surface-border/50 rounded-lg">
              <FileCode className={cn('h-5 w-5', health?.embedding_provider === 'configured' ? 'text-green-400' : 'text-yellow-400')} />
              <div>
                <p className="text-sm font-medium text-text-primary">Embeddings</p>
                <p className="text-xs text-text-secondary">
                  {health?.embedding_provider === 'configured' ? 'Configured' : 'Not configured'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-surface-border/50 rounded-lg">
              <Shield className={cn('h-5 w-5', health?.status === 'healthy' ? 'text-green-400' : health?.status === 'degraded' ? 'text-yellow-400' : 'text-red-400')} />
              <div>
                <p className="text-sm font-medium text-text-primary">Overall Health</p>
                <p className="text-xs text-text-secondary capitalize">{health?.status || 'Unknown'}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-4">
            <div className="p-3 bg-blue-500/10 rounded-xl">
              <Database className="h-6 w-6 text-blue-400" />
            </div>
            <div>
              <p className="text-3xl font-bold text-text-primary">{stats.totalRepos}</p>
              <p className="text-sm text-text-secondary">Total Repositories</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-4">
            <div className="p-3 bg-green-500/10 rounded-xl">
              <CheckCircle className="h-6 w-6 text-green-400" />
            </div>
            <div>
              <p className="text-3xl font-bold text-text-primary">{stats.indexedRepos}</p>
              <p className="text-sm text-text-secondary">Indexed</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-4">
            <div className="p-3 bg-blue-500/10 rounded-xl">
              <Loader2 className="h-6 w-6 text-blue-400" />
            </div>
            <div>
              <p className="text-3xl font-bold text-text-primary">{stats.processingRepos}</p>
              <p className="text-sm text-text-secondary">Processing</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-4">
            <div className="p-3 bg-red-500/10 rounded-xl">
              <XCircle className="h-6 w-6 text-red-400" />
            </div>
            <div>
              <p className="text-3xl font-bold text-text-primary">{stats.failedRepos}</p>
              <p className="text-sm text-text-secondary">Failed</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Repositories */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FileCode className="h-5 w-5" />
            Recent Repositories
          </CardTitle>
          <Link to="/repositories" className="text-sm text-accent hover:text-accent-light font-medium">
            View all →
          </Link>
        </CardHeader>
        <CardContent>
          {repositories.length === 0 ? (
            <div className="text-center py-12">
              <Database className="h-12 w-12 text-text-muted mx-auto mb-4" />
              <h3 className="text-lg font-medium text-text-primary mb-2">No repositories yet</h3>
              <p className="text-text-secondary mb-6">Upload your first repository to get started</p>
              <Link to="/repositories" className="btn-primary">
                <Upload className="h-4 w-4" />
                Upload Repository
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {repositories.slice(0, 5).map((repo) => (
                <div
                  key={repo.id}
                  className="flex items-center justify-between p-3 bg-surface-border/30 rounded-lg hover:bg-surface-border/50 transition-colors"
                >
                  <Link to={`/repositories/${repo.id}`} className="flex items-center gap-4 flex-1 min-w-0">
                    <div className="p-2 bg-accent/10 rounded-lg">
                      <FileCode className="h-5 w-5 text-accent" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-text-primary truncate">{repo.display_name}</p>
                      <div className="flex items-center gap-2 mt-1 text-xs text-text-muted">
                        <Badge variant={repo.status as any} className="gap-1">
                          {getStatusIcon(repo.status)}
                          {repo.status.charAt(0).toUpperCase() + repo.status.slice(1)}
                        </Badge>
                        {repo.detected_languages.length > 0 && (
                          <span>{repo.detected_languages.slice(0, 3).join(', ')}</span>
                        )}
                        <span>{repo.file_count} files</span>
                      </div>
                    </div>
                  </Link>
                  <div className="flex items-center gap-2 ml-4">
                    <span className="text-xs text-text-muted">{formatRelativeTime(repo.updated_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}