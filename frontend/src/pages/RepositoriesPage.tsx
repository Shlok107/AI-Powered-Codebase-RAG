import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Repository } from '../types'
import { Card, CardContent, Badge, Button, Input, Modal, Select } from '../components'
import { formatRelativeTime, formatFileSize, getLanguageLabel } from '../utils/format'
import { cn } from '../utils/cn'
import {
  Plus,
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
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
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
      const res = await api.listRepositories({ limit: 100 })
      setRepositories(res.repositories)
    } catch (err) {
      console.error(err)
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
      await fetchRepositories()
      navigate(`/repositories/${repo.id}`)
    } catch (err) {
      console.error(err)
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
    } catch (err) {
      console.error(err)
    } finally {
      setDeleting(false)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'indexed': return <CheckCircle className="h-4 w-4 text-green-400" />
      case 'processing': return <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />
      case 'failed': return <XCircle className="h-4 w-4 text-red-400" />
      default: return <AlertCircle className="h-4 w-4 text-yellow-400" />
    }
  }

  const filteredRepos = repositories
    .filter((repo) => {
      if (statusFilter !== 'all' && repo.status !== statusFilter) return false
      if (searchQuery && !repo.display_name.toLowerCase().includes(searchQuery.toLowerCase())) return false
      return true
    })
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())

  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Repositories</h1>
          <p className="text-text-secondary mt-1">Manage and browse your code repositories</p>
        </div>
        <Button onClick={() => setUploadModalOpen(true)}>
          <Upload className="h-4 w-4" />
          Upload Repository
        </Button>
      </div>

      {/* Search and Filters */}
      <Card padding="md">
        <CardContent className="flex flex-wrap gap-4">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
            <Input
              placeholder="Search repositories..."
              value={searchQuery}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          <Select
            value={statusFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setStatusFilter(e.target.value)}
            options={statuses.map((s) => ({ value: s, label: s.charAt(0).toUpperCase() + s.slice(1) }))}
            placeholder="All statuses"
            className="w-auto min-w-[150px]"
          />
          <Button variant="ghost" onClick={fetchRepositories} disabled={loading}>
            <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            Refresh
          </Button>
        </CardContent>
      </Card>

      {/* Repository List */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-accent mx-auto mb-4" />
              <p className="text-text-secondary">Loading repositories...</p>
            </div>
          ) : filteredRepos.length === 0 ? (
            <div className="text-center py-16">
              <FileCode className="h-12 w-12 text-text-muted mx-auto mb-4" />
              <h3 className="text-lg font-medium text-text-primary mb-2">
                {searchQuery || statusFilter !== 'all' ? 'No matching repositories' : 'No repositories yet'}
              </h3>
              <p className="text-text-secondary mb-6">
                {searchQuery || statusFilter !== 'all'
                  ? 'Try adjusting your search or filters'
                  : 'Upload your first repository to get started'}
              </p>
              {(!searchQuery && statusFilter === 'all') && (
                <Button onClick={() => setUploadModalOpen(true)}>
                  <Upload className="h-4 w-4" />
                  Upload Repository
                </Button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-surface-border">
              {filteredRepos.map((repo) => (
                <Link
                  key={repo.id}
                  to={`/repositories/${repo.id}`}
                  className="flex items-center justify-between p-4 hover:bg-surface-hover/50 transition-colors group"
                >
                  <div className="flex items-center gap-4 min-w-0 flex-1">
                    <div className="p-2 bg-accent/10 rounded-lg flex-shrink-0">
                      <FileCode className="h-5 w-5 text-accent" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-text-primary truncate">{repo.display_name}</p>
                      <div className="flex items-center gap-2 mt-1 text-xs text-text-muted flex-wrap">
                        <Badge variant={repo.status as any} className="gap-1">
                          {getStatusIcon(repo.status)}
                          {repo.status.charAt(0).toUpperCase() + repo.status.slice(1)}
                        </Badge>
                        {repo.detected_languages.length > 0 && (
                          <>
                            {repo.detected_languages.slice(0, 4).map((lang) => (
                              <Badge key={lang} variant="default" className="text-xs">
                                {getLanguageLabel(lang)}
                              </Badge>
                            ))}
                            {repo.detected_languages.length > 4 && (
                              <Badge variant="default" className="text-xs">
                                +{repo.detected_languages.length - 4} more
                              </Badge>
                            )}
                          </>
                        )}
                        <span>{repo.file_count} files</span>
                        {repo.chunk_count > 0 && <span>{repo.chunk_count} chunks</span>}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-text-muted ml-4">
                    <span className="text-xs">{formatRelativeTime(repo.updated_at)}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e: React.MouseEvent) => {
                        e.preventDefault()
                        e.stopPropagation()
                        setRepoToDelete(repo)
                        setDeleteModalOpen(true)
                      }}
                      className="text-text-muted hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100"
                      aria-label={`Delete ${repo.display_name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

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
            <div className="border-2 border-dashed border-surface-border rounded-xl p-8 text-center hover:border-accent/50 transition-colors">
              <input
                type="file"
                accept=".zip"
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  const file = e.target.files?.[0]
                  if (file) setSelectedFile(file)
                }}
                className="hidden"
                id="zip-upload"
                disabled={uploading}
              />
              <label htmlFor="zip-upload" className="cursor-pointer">
                <Upload className="h-12 w-12 text-text-muted mx-auto mb-4" />
                <p className="text-text-secondary mb-2">Drag and drop a ZIP file here, or click to browse</p>
                <p className="text-xs text-text-muted">Max 50MB • Source code only</p>
              </label>
              {selectedFile && (
                <div className="mt-4 p-3 bg-surface rounded-lg text-left">
                  <p className="font-medium text-text-primary">{selectedFile.name}</p>
                  <p className="text-sm text-text-secondary">{formatFileSize(selectedFile.size)}</p>
                </div>
              )}
            </div>
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
        }}
        title="Delete Repository"
        description={repoToDelete ? `Are you sure you want to delete "${repoToDelete.display_name}"? This action cannot be undone.` : ''}
        size="sm"
      >
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => { setDeleteModalOpen(false); setRepoToDelete(null) }}>
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