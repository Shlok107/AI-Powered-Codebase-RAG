import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Repository, SecurityFinding, SecurityScan } from '../types'
import { Card, CardHeader, CardTitle, CardContent, Badge, Button, Select, Modal, Input } from '../components'
import { formatRelativeTime, getSeverityColor } from '../utils/format'
import { cn } from '../utils/cn'
import {
  Shield,
  AlertCircle,
  CheckCircle,
  XCircle,
  Info,
  Search,
  RefreshCw,
  Play,
  Loader2,
  ChevronLeft,
  Eye,
} from 'lucide-react'
import { Link } from 'react-router-dom'

const severityOptions = ['all', 'critical', 'high', 'medium', 'low', 'info']
const categoryOptions = ['all', 'secrets', 'dangerous_code', 'dependencies', 'infrastructure', 'configuration']
const statusOptions = ['all', 'open', 'dismissed', 'resolved']

export function SecurityPage() {
  const { repositoryId } = useParams<{ repositoryId: string }>()
  const navigate = useNavigate()
  const [repository, setRepository] = useState<Repository | null>(null)
  const [scans, setScans] = useState<SecurityScan[]>([])
  const [findings, setFindings] = useState<SecurityFinding[]>([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [selectedFinding, setSelectedFinding] = useState<SecurityFinding | null>(null)
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  useEffect(() => {
    if (repositoryId) {
      fetchData()
    }
  }, [repositoryId])

  async function fetchData() {
    try {
      setLoading(true)
      const [repo, scansRes, findingsRes] = await Promise.all([
        api.getRepository(repositoryId!),
        api.listScans(repositoryId!),
        api.listFindings(repositoryId!),
      ])
      setRepository(repo)
      setScans(scansRes)
      setFindings(findingsRes.findings)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  async function handleScan() {
    try {
      setScanning(true)
      await api.runScan(repositoryId!)
      await fetchData()
    } catch (err) {
      console.error(err)
    } finally {
      setScanning(false)
    }
  }

  async function handleStatusChange(findingId: string, status: 'open' | 'dismissed' | 'resolved') {
    try {
      await api.updateFinding(findingId, status)
      setFindings((prev) =>
        prev.map((f) => (f.id === findingId ? { ...f, status } : f))
      )
      if (selectedFinding?.id === findingId) {
        setSelectedFinding((prev) => (prev ? { ...prev, status } : null))
      }
    } catch (err) {
      console.error(err)
    }
  }

  const getScanStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-400" />
      case 'processing': return <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />
      case 'failed': return <XCircle className="h-4 w-4 text-red-400" />
      default: return <Info className="h-4 w-4 text-yellow-400" />
    }
  }

  const severityCounts = findings.reduce(
    (acc, f) => {
      acc[f.severity] = (acc[f.severity] || 0) + 1
      return acc
    },
    {} as Record<string, number>
  )

  const filteredFindings = findings
    .filter((f) => {
      if (severityFilter !== 'all' && f.severity !== severityFilter) return false
      if (categoryFilter !== 'all' && f.category !== categoryFilter) return false
      if (statusFilter !== 'all' && f.status !== statusFilter) return false
      if (searchQuery && !f.title.toLowerCase().includes(searchQuery.toLowerCase()) &&
          !f.file_path?.toLowerCase().includes(searchQuery.toLowerCase()) &&
          !f.rule_id.toLowerCase().includes(searchQuery.toLowerCase())) return false
      return true
    })
    .sort((a, b) => {
      const severityOrder = { critical: 0, high: 1, medium: 2, low: 3, info: 4 }
      return (severityOrder[a.severity] || 5) - (severityOrder[b.severity] || 5)
    })

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-accent" />
      </div>
    )
  }

  if (!repository) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-text-muted mx-auto mb-4" />
          <h3 className="text-lg font-medium text-text-primary mb-2">Repository not found</h3>
          <Button onClick={() => navigate('/repositories')}>Back to Repositories</Button>
        </div>
      </div>
    )
  }

  const latestScan = scans[0]

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <Link to="/repositories" className="btn-ghost">
            <ChevronLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Security Findings</h1>
            <p className="text-text-secondary mt-1">{repository.display_name}</p>
          </div>
        </div>
        <Button onClick={handleScan} disabled={scanning || latestScan?.status === 'processing'}>
          <Play className="h-4 w-4" />
          {scanning ? 'Scanning...' : latestScan?.status === 'processing' ? 'Scan in Progress' : 'Run Security Scan'}
        </Button>
      </div>

      {/* Repository Status */}
      <Card padding="md" className="mb-4">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-accent/10 rounded-lg">
              <Shield className="h-5 w-5 text-accent" />
            </div>
            <div>
              <h3 className="font-medium text-text-primary">Last Scan</h3>
              <p className="text-sm text-text-secondary">
                {latestScan
                  ? `${getScanStatusIcon(latestScan.status)} ${latestScan.status.charAt(0).toUpperCase() + latestScan.status.slice(1)} • ${formatRelativeTime(latestScan.updated_at)}`
                  : 'No scans yet'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-text-muted">Total Findings:</span>
              <span className="text-lg font-bold text-text-primary">{findings.length}</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Severity Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Findings by Severity
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[
              { key: 'critical', label: 'Critical', color: 'red' },
              { key: 'high', label: 'High', color: 'orange' },
              { key: 'medium', label: 'Medium', color: 'yellow' },
              { key: 'low', label: 'Low', color: 'green' },
              { key: 'info', label: 'Info', color: 'blue' },
            ].map(({ key, label, color }) => (
              <Link
                key={key}
                to="#"
                onClick={(e) => {
                  e.preventDefault()
                  setSeverityFilter(severityFilter === key ? 'all' : key)
                }}
                className={cn(
                  'p-4 rounded-xl transition-all',
                  severityFilter === key ? 'ring-2 ring-accent bg-accent/5' : 'bg-surface-border/30 hover:bg-surface-border/50'
                )}
              >
                <div className="flex items-center justify-between">
                  <span className={cn('text-sm font-medium', getSeverityColor(key))}>{label}</span>
                  <span className="text-2xl font-bold text-text-primary">{severityCounts[key] || 0}</span>
                </div>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <Card padding="md">
        <CardContent className="flex flex-wrap gap-4">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
            <Input
              placeholder="Search findings..."
              value={searchQuery}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          <Select
            value={severityFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSeverityFilter(e.target.value)}
            options={severityOptions.map((s) => ({ value: s, label: s === 'all' ? 'All Severities' : s.charAt(0).toUpperCase() + s.slice(1) }))}
            placeholder="All Severities"
            className="w-auto min-w-[150px]"
          />
          <Select
            value={categoryFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCategoryFilter(e.target.value)}
            options={categoryOptions.map((c) => ({ value: c, label: c === 'all' ? 'All Categories' : c.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) }))}
            placeholder="All Categories"
            className="w-auto min-w-[180px]"
          />
          <Select
            value={statusFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setStatusFilter(e.target.value)}
            options={statusOptions.map((s) => ({ value: s, label: s === 'all' ? 'All Statuses' : s.charAt(0).toUpperCase() + s.slice(1) }))}
            placeholder="All Statuses"
            className="w-auto min-w-[150px]"
          />
          <Button variant="ghost" onClick={fetchData} disabled={loading}>
            <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            Refresh
          </Button>
        </CardContent>
      </Card>

      {/* Findings List */}
      <Card>
        <CardContent className="p-0">
          {filteredFindings.length === 0 ? (
            <div className="text-center py-16">
              <Shield className="h-12 w-12 text-text-muted mx-auto mb-4" />
              <h3 className="text-lg font-medium text-text-primary mb-2">
                {searchQuery || severityFilter !== 'all' || categoryFilter !== 'all' || statusFilter !== 'all'
                  ? 'No matching findings'
                  : 'No security findings'}
              </h3>
              <p className="text-text-secondary">
                {searchQuery || severityFilter !== 'all' || categoryFilter !== 'all' || statusFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : 'Run a security scan to find potential issues'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-surface-border">
              {filteredFindings.map((finding) => (
                <button
                  key={finding.id}
                  onClick={() => {
                    setSelectedFinding(finding)
                    setDetailDrawerOpen(true)
                  }}
                  className="w-full p-4 text-left hover:bg-surface-hover/50 transition-colors flex items-start justify-between gap-4"
                >
                  <div className="flex items-start gap-3 min-w-0 flex-1">
                    <Badge variant={finding.severity as any} className="flex-shrink-0 mt-0.5">
                      {finding.severity.charAt(0).toUpperCase() + finding.severity.slice(1)}
                    </Badge>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-medium text-text-primary truncate">{finding.title}</p>
                        <Badge variant="default" className="text-xs">{finding.category.replace('_', ' ')}</Badge>
                        <Badge variant={finding.confidence as any} className="text-xs">{finding.confidence} confidence</Badge>
                        <Badge variant={finding.status as any} className="text-xs">{finding.status}</Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-text-muted flex-wrap">
                        {finding.file_path && (
                          <span className="font-mono truncate max-w-[300px]">
                            {finding.file_path}:{finding.start_line || 1}-{finding.end_line || '?'}
                          </span>
                        )}
                        <span>{finding.rule_id}</span>
                        <span>{formatRelativeTime(finding.created_at)}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Eye className="h-4 w-4 text-text-muted" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Finding Detail Drawer */}
      <Modal
        isOpen={detailDrawerOpen}
        onClose={() => {
          setDetailDrawerOpen(false)
          setSelectedFinding(null)
        }}
        title="Finding Details"
        size="lg"
      >
        {selectedFinding && (
          <div className="space-y-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  <Badge variant={selectedFinding.severity as any}>
                    {selectedFinding.severity.charAt(0).toUpperCase() + selectedFinding.severity.slice(1)}
                  </Badge>
                  <Badge variant="default">{selectedFinding.category.replace('_', ' ')}</Badge>
                  <Badge variant={selectedFinding.confidence as any}>{selectedFinding.confidence} confidence</Badge>
                  <Badge variant={selectedFinding.status as any}>{selectedFinding.status}</Badge>
                </div>
                <h3 className="text-lg font-medium text-text-primary">{selectedFinding.title}</h3>
                <p className="text-sm text-text-secondary mt-1">Rule: {selectedFinding.rule_id}</p>
              </div>
              <Select
                value={selectedFinding.status}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => handleStatusChange(selectedFinding.id, e.target.value as any)}
                options={statusOptions.filter(s => s !== 'all').map(s => ({ value: s, label: s.charAt(0).toUpperCase() + s.slice(1) }))}
                className="w-auto"
              />
            </div>

            {selectedFinding.file_path && (
              <div className="space-y-2">
                <p className="font-medium text-text-secondary">Location</p>
                <div className="flex items-center gap-2 text-sm text-text-primary font-mono bg-background p-3 rounded-lg border border-surface-border">
                  {selectedFinding.file_path}:{selectedFinding.start_line || 1}-{selectedFinding.end_line || '?'}
                </div>
              </div>
            )}

            <div className="space-y-2">
              <p className="font-medium text-text-secondary">Explanation</p>
              <p className="text-text-primary">{selectedFinding.explanation}</p>
            </div>

            <div className="space-y-2">
              <p className="font-medium text-text-secondary">Remediation</p>
              <p className="text-text-primary">{selectedFinding.remediation}</p>
            </div>

            {selectedFinding.redacted_evidence && (
              <div className="space-y-2">
                <p className="font-medium text-text-secondary">Evidence (Redacted)</p>
                <pre className="code-block whitespace-pre-wrap text-sm">{selectedFinding.redacted_evidence}</pre>
              </div>
            )}

            {selectedFinding.references.length > 0 && (
              <div className="space-y-2">
                <p className="font-medium text-text-secondary">References</p>
                <ul className="space-y-1">
                  {selectedFinding.references.map((ref, idx) => (
                    <li key={idx}>
                      <a href={ref} target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent-light text-sm">
                        {ref}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}