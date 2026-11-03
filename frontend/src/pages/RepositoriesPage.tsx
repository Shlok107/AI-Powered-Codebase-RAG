import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Repository } from '../types'
import { Badge, Button, Input, Modal, Select } from '../components'
import { formatRelativeTime, formatFileSize, getLanguageLabel, getErrorMessage } from '../utils/format'
import { cn } from '../utils/cn'
import {
  Upload,
  RefreshCw,
  Trash2,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  FileCode,
  Search,
} from 'lucide-react'

export function RepositoriesPage() {
  const navigate = useNavigate()
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [repositoryTotal, setRepositoryTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [languageFilter, setLanguageFilter] = useState<string>('all')
  const [dragActive, setDragActive] = useState(false)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [deleteError, setDeleteError] = useState('')
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [repoToDelete, setRepoToDelete] = useState<Repository | null>(null)
  const [deleting, setDeleting] = useState(false)

  const statuses = ['all', 'pending', 'processing', 'indexed', 'failed']

  useEffect(() => {
    fetchRepositories()
  }, [])

  async function fetchRepositories() {
    try {
      setLoading(true)
      setListError('')
      const res = await api.listRepositories({ limit: 100 })
      setRepositories(res.repositories)
      setRepositoryTotal(res.total)
    } catch (err) {
      console.error(err)
      setListError(getErrorMessage(err, 'Could not load repositories. Check the API connection and try again.'))
    } finally {
      setLoading(false)
    }
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedFile) return

    try {
      setUploading(true)
      setUploadProgress(0)
      const repo = await api.uploadRepository(selectedFile, setUploadProgress)
      setUploadModalOpen(false)
      setSelectedFile(null)
      setUploadError('')
      await fetchRepositories()
      navigate(`/repositories/${repo.id}`, { state: { uploadCompleted: true } })
    } catch (err) {
      console.error(err)
      setUploadError(getErrorMessage(err, 'Upload failed. Check the ZIP file and try again.'))
    } finally {
      setUploading(false)
      setUploadProgress(0)
    }
  }

  async function handleDelete() {
    if (!repoToDelete) return
    try {
      setDeleting(true)
      await api.deleteRepository(repoToDelete.id)
      setDeleteModalOpen(false)
      setRepositories((prev) => prev.filter((r) => r.id !== repoToDelete.id))
      setRepositoryTotal((current) => Math.max(0, current - 1))
    } catch (err) {
      console.error(err)
      setDeleteError(getErrorMessage(err, 'Could not delete this repository. Please try again.'))
    } finally {
      setDeleting(false)
    }
  }

  function chooseFile(file?: File) {
    if (!file) return
    setUploadError('')
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setSelectedFile(null)
      setUploadError('Choose a ZIP archive to upload.')
      return
    }
    if (file.size > 50 * 1024 * 1024) {
      setSelectedFile(null)
      setUploadError('This file exceeds the 50 MB upload limit.')
      return
    }
    setSelectedFile(file)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'indexed': return <CheckCircle className="h-4 w-4 text-status-success" />
      case 'processing': return <Loader2 className="h-4 w-4 text-status-cyan animate-spin" />
      case 'failed': return <XCircle className="h-4 w-4 text-status-danger" />
      default: return <AlertCircle className="h-4 w-4 text-status-warning" />
    }
  }

  const languages = Array.from(new Set(repositories.flatMap((repo) => repo.detected_languages))).sort()

  const filteredRepos = repositories
    .filter((repo) => {
      if (statusFilter !== 'all' && repo.status !== statusFilter) return false
      if (languageFilter !== 'all' && !repo.detected_languages.includes(languageFilter)) return false
      const query = searchQuery.trim().toLowerCase()
      if (query && !repo.display_name.toLowerCase().includes(query) && !repo.detected_languages.some((language) => language.toLowerCase().includes(query))) return false
      return true
    })
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())

  return (
    <div className="space-y-5 animate-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-[.15em] text-text-muted mb-1">Workspace / Source</p>
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">Repositories</h1>
          <p className="text-sm text-text-secondary mt-1">Browse indexed source, monitor ingestion, and manage repository uploads.</p>
        </div>
        <Button size="sm" onClick={() => setUploadModalOpen(true)}>
          <Upload className="h-4 w-4" />
          Add repository
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-y border-surface-border py-2.5">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
            <Input
              aria-label="Search repositories"
              placeholder="Filter by repository or language…"
              value={searchQuery}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 text-sm"
            />
          </div>
          <Select
            aria-label="Filter by status"
            value={statusFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setStatusFilter(e.target.value)}
            options={statuses.map((s) => ({ value: s, label: s.charAt(0).toUpperCase() + s.slice(1) }))}
            className="w-auto min-w-[130px] h-9 text-sm"
          />
          <Select
            aria-label="Filter by language"
            value={languageFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setLanguageFilter(e.target.value)}
            options={[{ value: 'all', label: 'All languages' }, ...languages.map((language) => ({ value: language, label: getLanguageLabel(language) }))]}
            className="w-auto min-w-[145px] h-9 text-sm"
          />
          <Button variant="ghost" size="sm" onClick={fetchRepositories} disabled={loading}>
            <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <span className="ml-auto w-full text-right text-[11px] text-text-muted sm:w-auto">Showing {filteredRepos.length} of {repositories.length} loaded · {repositoryTotal} total</span>
      </div>

      {/* Repository List */}
      <section aria-label="Repository list" className="border-b border-surface-border">
          {listError ? (
            <div className="p-8 text-center"><AlertCircle className="h-6 w-6 text-red-300 mx-auto mb-3" /><p className="text-sm text-red-300" role="alert">{listError}</p><Button variant="secondary" size="sm" className="mt-4" onClick={fetchRepositories}>Retry</Button></div>
          ) : loading ? (
            <div className="p-8 text-center" role="status">
              <Loader2 className="h-5 w-5 animate-spin text-accent mx-auto mb-3" />
              <p className="text-sm text-text-secondary">Loading repositories…</p>
            </div>
          ) : filteredRepos.length === 0 ? (
            <div className="text-center py-14 px-5">
              <FileCode className="h-8 w-8 text-text-muted mx-auto mb-3" />
              <h3 className="text-base font-medium text-text-primary mb-1">
                {searchQuery || statusFilter !== 'all' || languageFilter !== 'all' ? 'No matching repositories' : 'No repositories yet'}
              </h3>
              <p className="text-sm text-text-secondary mb-5">
                {searchQuery || statusFilter !== 'all' || languageFilter !== 'all'
                  ? 'Try adjusting your search or filters'
                  : 'Upload your first repository to get started'}
              </p>
              {(!searchQuery && statusFilter === 'all' && languageFilter === 'all') && (
                <Button size="sm" onClick={() => setUploadModalOpen(true)}>
                  <Upload className="h-4 w-4" />
                  Add repository
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead><tr className="border-b border-surface-border text-[10px] uppercase tracking-[.12em] text-text-muted">
                  <th scope="col" className="py-2.5 pl-3 pr-4 font-semibold">Repository</th>
                  <th scope="col" className="px-3 py-2.5 font-semibold">Status</th>
                  <th scope="col" className="px-3 py-2.5 font-semibold">Languages</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-semibold">Files / chunks</th>
                  <th scope="col" className="px-3 py-2.5 font-semibold">Updated</th>
                  <th scope="col" className="w-12 px-2 py-2.5"><span className="sr-only">Actions</span></th>
                </tr></thead>
                <tbody className="divide-y divide-surface-border/80">
                  {filteredRepos.map((repo) => (
                    <tr key={repo.id} className="group hover:bg-surface-hover/40">
                      <td className="py-2.5 pl-3 pr-4">
                        <Link to={`/repositories/${repo.id}`} className="flex items-center gap-2.5 min-w-0 rounded-sm focus-visible:outline-accent">
                          <span className="h-7 w-7 shrink-0 rounded bg-background-tertiary flex items-center justify-center"><FileCode className="h-3.5 w-3.5 text-accent" /></span>
                          <span className="min-w-0"><span className="block truncate font-medium text-text-primary">{repo.display_name}</span><span className="block truncate font-mono text-[10px] text-text-muted">{repo.source_type === 'zip_upload' ? 'ZIP upload' : repo.source_type}</span></span>
                        </Link>
                      </td>
                      <td className="px-3 py-2.5"><Badge variant={repo.status as any} className="whitespace-nowrap"><span className={cn('h-1.5 w-1.5 rounded-full', repo.status === 'indexed' ? 'bg-emerald-300' : repo.status === 'processing' ? 'bg-sky-300 animate-pulse' : repo.status === 'failed' ? 'bg-red-300' : 'bg-text-muted')} />{repo.status}</Badge></td>
                      <td className="px-3 py-2.5"><div className="flex max-w-[250px] flex-wrap gap-1">{repo.detected_languages.slice(0, 3).map((language) => <span key={language} className="text-[11px] text-text-secondary">{getLanguageLabel(language)}{repo.detected_languages.indexOf(language) < Math.min(repo.detected_languages.length, 3) - 1 ? ',' : ''}</span>)}{repo.detected_languages.length > 3 && <span className="text-[11px] text-text-muted">+{repo.detected_languages.length - 3}</span>}{repo.detected_languages.length === 0 && <span className="text-[11px] text-text-muted">—</span>}</div></td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-text-secondary">{repo.file_count.toLocaleString()} <span className="text-text-muted">/ {repo.chunk_count.toLocaleString()}</span></td>
                      <td className="px-3 py-2.5 whitespace-nowrap text-xs text-text-muted">{formatRelativeTime(repo.updated_at)}</td>
                      <td className="px-2 py-2.5 text-right"><Button variant="ghost" size="sm" onClick={() => { setRepoToDelete(repo); setDeleteModalOpen(true) }} className="h-7 w-7 p-0 text-text-muted hover:text-red-300 hover:bg-red-500/10 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 group-focus-within:opacity-100" aria-label={`Delete ${repo.display_name}`} title={`Delete ${repo.display_name}`}><Trash2 className="h-3.5 w-3.5" /></Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </section>

      {/* Upload Modal */}
      <Modal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        title="Upload Repository"
        description="Select a ZIP file containing your source code. Maximum 50MB."
        size="md"
      >
        <form onSubmit={handleUpload}>
          <div className="space-y-4">
            <div onDragEnter={(e) => { e.preventDefault(); setDragActive(true) }} onDragOver={(e) => e.preventDefault()} onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragActive(false) }} onDrop={(e) => { e.preventDefault(); setDragActive(false); chooseFile(e.dataTransfer.files[0]) }} className={cn('border border-dashed rounded-md p-6 sm:p-8 text-center transition-colors bg-background/40', dragActive ? 'border-accent bg-accent/5' : 'border-surface-border hover:border-accent/50')}>
              <input
                type="file"
                accept=".zip"
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  const file = e.target.files?.[0]
                  chooseFile(file)
                }}
                className="sr-only"
                id="zip-upload"
                disabled={uploading}
              />
              <label htmlFor="zip-upload" className="cursor-pointer">
                <Upload className="h-8 w-8 text-accent mx-auto mb-3" />
                <p className="text-sm text-text-primary mb-1">Drop a ZIP archive here</p>
                <p className="text-xs text-text-muted">or browse files · ZIP only · maximum 50 MB</p>
              </label>
              <button type="button" onClick={() => document.getElementById('zip-upload')?.click()} disabled={uploading} className="mt-3 text-xs font-medium text-accent hover:text-accent-light focus-visible:outline-accent disabled:opacity-50">Browse files</button>
              {selectedFile && (
                <div className="mt-4 p-3 bg-surface rounded-md text-left border border-surface-border">
                  <p className="truncate font-mono text-xs font-medium text-text-primary">{selectedFile.name}</p>
                  <p className="mt-1 text-xs text-text-secondary">{formatFileSize(selectedFile.size)} · Ready to upload</p>
                </div>
              )}
            </div>
            {uploadError && <p className="text-sm text-red-300" role="alert">{uploadError}</p>}
            {uploading && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">Uploading...</span>
                  <span className="text-text-primary">{uploadProgress}%</span>
                </div>
                <div className="h-2 bg-surface-border rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}
            <div className="flex justify-end gap-3 pt-4">
              <Button type="button" variant="secondary" onClick={() => setUploadModalOpen(false)} disabled={uploading}>
                Cancel
              </Button>
              <Button type="submit" disabled={uploading || !selectedFile}>
                {uploading ? 'Uploading...' : 'Upload'}
              </Button>
            </div>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false)
          setRepoToDelete(null)
        setDeleteError('')
        }}
        title="Delete Repository"
        description={repoToDelete ? `Are you sure you want to delete "${repoToDelete.display_name}"? This action cannot be undone.` : ''}
        size="sm"
      >
        {deleteError && <p className="text-sm text-red-300 mb-4" role="alert">{deleteError}</p>}
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => { setDeleteModalOpen(false); setRepoToDelete(null); setDeleteError('') }}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDelete} disabled={deleting}>
            {deleting ? 'Deleting...' : 'Delete'}
          </Button>
        </div>
      </Modal>
    </div>
  )
}
