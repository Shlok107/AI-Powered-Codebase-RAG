import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Repository } from '../types'
import { Card, CardHeader, CardTitle, CardContent, Badge, Button } from '../components'
import { formatRelativeTime, getLanguageLabel } from '../utils/format'
import { cn } from '../utils/cn'
import {
  MessageSquare,
  ChevronLeft,
  Search,
  Loader2,
  FileCode,
} from 'lucide-react'

export function ChatSelectorPage() {
  const navigate = useNavigate()
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    fetchRepositories()
  }, [])

  async function fetchRepositories() {
    try {
      setLoading(true)
      const res = await api.listRepositories({ limit: 100 })
      // Only show indexed repositories for chat
      setRepositories(res.repositories.filter(r => r.status === 'indexed'))
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const filteredRepos = repositories
    .filter((repo) => {
      if (searchQuery && !repo.display_name.toLowerCase().includes(searchQuery.toLowerCase())) return false
      return true
    })
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-accent" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <Link to="/repositories" className="btn-ghost">
            <ChevronLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Ask Codebase</h1>
            <p className="text-text-secondary mt-1">Select a repository to start asking questions</p>
          </div>
        </div>
      </div>

      {/* Search */}
      <Card padding="md">
        <CardContent>
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
            <input
              type="text"
              placeholder="Search repositories..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 px-3 py-2 rounded-lg bg-background border border-surface-border text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
            />
          </div>
        </CardContent>
      </Card>

      {/* Repository Grid */}
      <Card>
        <CardContent className="p-0">
          {filteredRepos.length === 0 ? (
            <div className="text-center py-16">
              <FileCode className="h-12 w-12 text-text-muted mx-auto mb-4" />
              <h3 className="text-lg font-medium text-text-primary mb-2">
                {searchQuery ? 'No matching repositories' : 'No indexed repositories'}
              </h3>
              <p className="text-text-secondary mb-6">
                {searchQuery
                  ? 'Try adjusting your search'
                  : 'Upload and index a repository first to start asking questions'}
              </p>
              {!searchQuery && (
                <Link to="/repositories" className="btn-primary">
                  <MessageSquare className="h-4 w-4" />
                  Go to Repositories
                </Link>
              )}
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filteredRepos.map((repo) => (
                <Link
                  key={repo.id}
                  to={`/chat/${repo.id}`}
                  className="p-4 bg-surface-border/30 rounded-xl hover:bg-surface-border/50 hover:border-accent/30 border border-transparent transition-all group"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-accent/10 rounded-lg">
                      <MessageSquare className="h-5 w-5 text-accent" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-text-primary truncate">{repo.display_name}</p>
                      <div className="flex items-center gap-2 mt-1 text-xs text-text-muted flex-wrap">
                        <Badge variant={repo.status as any} className="gap-1">
                          {repo.status.charAt(0).toUpperCase() + repo.status.slice(1)}
                        </Badge>
                        {repo.detected_languages.length > 0 && (
                          <>
                            {repo.detected_languages.slice(0, 3).map((lang) => (
                              <Badge key={lang} variant="default" className="text-xs">
                                {getLanguageLabel(lang)}
                              </Badge>
                            ))}
                            {repo.detected_languages.length > 3 && (
                              <Badge variant="default" className="text-xs">
                                +{repo.detected_languages.length - 3} more
                              </Badge>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs text-text-muted">
                    <span>{repo.file_count} files</span>
                    <span>{repo.chunk_count} chunks</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}