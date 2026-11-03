import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Repository } from '../types'
import { Badge, Button, Input } from '../components'
import { getErrorMessage, getLanguageLabel } from '../utils/format'
import {
  Shield,
  Search,
  Loader2,
  FileCode,
  ArrowUpRight,
} from 'lucide-react'

export function SecuritySelectorPage() {
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    fetchRepositories()
  }, [])

  async function fetchRepositories() {
    try {
      setLoading(true)
      setError('')
      const res = await api.listRepositories({ limit: 100 })
      setRepositories(res.repositories)
    } catch (err) {
      setError(getErrorMessage(err, 'Could not load repositories. Check the API connection and retry.'))
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
    <div className="space-y-5 animate-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div><p className="text-[10px] uppercase tracking-[.15em] text-text-muted mb-1">Security / Repository</p><h1 className="text-xl font-semibold tracking-tight text-text-primary">Security analysis</h1><p className="text-sm text-text-secondary mt-1">Choose a repository to review findings or run a scan.</p></div>
      </div>

      {/* Search */}
      <div className="relative max-w-2xl border-y border-surface-border py-2.5">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
            <Input
              aria-label="Search repositories"
              placeholder="Filter repositories…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 pl-9 text-sm"
            />
          </div>
      </div>

      {/* Repository Grid */}
      <section className="border-b border-surface-border" aria-label="Repositories available for security analysis">
          {error ? <div className="py-8 text-center" role="alert"><p className="text-sm text-red-300">{error}</p><Button size="sm" variant="secondary" className="mt-3" onClick={fetchRepositories}>Retry</Button></div> : null}
          {!error && (filteredRepos.length === 0 ? (
            <div className="text-center py-12">
              <FileCode className="h-7 w-7 text-text-muted mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-text-primary mb-1">
                {searchQuery ? 'No matching repositories' : 'No repositories yet'}
              </h3>
              <p className="text-xs text-text-secondary mb-4">
                {searchQuery
                  ? 'Try adjusting your search'
                  : 'Upload a repository first to run security scans'}
              </p>
              {!searchQuery && (
                <Link to="/repositories" className="btn-secondary text-xs">
                  <Shield className="h-4 w-4" />
                  Add repository <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              )}
            </div>
          ) : (
            <div className="divide-y divide-surface-border">{filteredRepos.map((repo) => <Link key={repo.id} to={`/security/${repo.id}`} className="flex items-center gap-3 px-3 py-2.5 hover:bg-surface-hover/40 focus-visible:bg-surface-hover/40">
              <span className="h-7 w-7 shrink-0 rounded bg-background-tertiary flex items-center justify-center"><Shield className="h-3.5 w-3.5 text-accent" /></span>
              <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-text-primary">{repo.display_name}</span><span className="mt-0.5 flex flex-wrap gap-x-2 text-[10px] text-text-muted">{repo.detected_languages.slice(0, 3).map((language) => <span key={language}>{getLanguageLabel(language)}</span>)}</span></span>
              <span className="hidden text-right text-[11px] text-text-muted sm:block">{repo.file_count.toLocaleString()} files<br />{repo.chunk_count.toLocaleString()} chunks</span><Badge variant={repo.status as any}>{repo.status}</Badge><ArrowUpRight className="h-3.5 w-3.5 text-text-muted" />
            </Link>)}</div>
          ))}
      </section>
    </div>
  )
}
