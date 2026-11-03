import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Repository, SecurityFinding, SecurityScan } from '../types'
import { Badge, Button, Select, Modal, Input } from '../components'
import { formatRelativeTime, getErrorMessage, getSeverityColor } from '../utils/format'
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
  const [findingsTotal, setFindingsTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [requestError, setRequestError] = useState('')
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
      setRequestError('')
      const [repo, scansRes, findingsRes] = await Promise.all([
        api.getRepository(repositoryId!),
        api.listScans(repositoryId!),
        api.listFindings(repositoryId!),
      ])
      setRepository(repo)
      setScans(scansRes)
      setFindings(findingsRes.findings)
      setFindingsTotal(findingsRes.total)
    } catch (err) {
      console.error(err)
      setRequestError(getErrorMessage(err, 'Could not load security data. Please try again.'))
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
      setRequestError(getErrorMessage(err, 'Security scan could not be started. Please try again.'))
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
      setRequestError(getErrorMessage(err, 'Could not update this finding. Please try again.'))
    }
  }

  const getScanStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-4 w-4 text-status-success" />
      case 'processing': return <Loader2 className="h-4 w-4 text-status-cyan animate-spin" />
      case 'failed': return <XCircle className="h-4 w-4 text-status-danger" />
      default: return <Info className="h-4 w-4 text-status-warning" />
    }
  }

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
      return (severityOrder[a.severity] ?? 5) - (severityOrder[b.severity] ?? 5)
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
  const severityCounts = latestScan ? {
    critical: latestScan.critical_count,
    high: latestScan.high_count,
    medium: latestScan.medium_count,
    low: latestScan.low_count,
    info: latestScan.info_count,
  } : findings.reduce((counts, finding) => ({ ...counts, [finding.severity]: (counts[finding.severity] || 0) + 1 }), {} as Record<string, number>)

  return (
    <div className="space-y-5 animate-in">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <Link to="/repositories" className="btn-ghost">
            <ChevronLeft className="h-4 w-4" />
          </Link>
          <div>
            <p className="text-[10px] uppercase tracking-[.15em] text-text-muted mb-1">Repository / Analysis</p>
            <h1 className="text-xl font-semibold tracking-tight text-text-primary">Security findings</h1>
            <p className="text-sm text-text-secondary mt-1">{repository.display_name}</p>
          </div>
        </div>
        <Button size="sm" onClick={handleScan} disabled={scanning || latestScan?.status === 'processing'}>
          <Play className="h-4 w-4" />
          {scanning ? 'Scanning...' : latestScan?.status === 'processing' ? 'Scan in Progress' : 'Run Security Scan'}
        </Button>
      </div>
      {requestError && <div className="rounded-md border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-300" role="alert">{requestError}</div>}

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-y border-surface-border py-2 text-xs">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="inline-flex items-center gap-1.5 text-text-secondary"><Shield className="h-3.5 w-3.5 text-accent" />Latest scan</span>
          {latestScan ? <span className="inline-flex items-center gap-1.5 text-text-primary">{getScanStatusIcon(latestScan.status)}<span className="capitalize">{latestScan.status}</span><span className="text-text-muted">· {formatRelativeTime(latestScan.updated_at)}</span></span> : <span className="text-text-muted">No scans yet</span>}
          <span className="text-text-muted">{findingsTotal.toLocaleString()} findings</span>
        </div>
        <span className="text-[10px] text-text-muted">Severity totals reflect the latest scan when available</span>
      </div>

      <div className="overflow-x-auto border-b border-surface-border">
        <div className="grid min-w-[580px] grid-cols-5 divide-x divide-surface-border border-t border-surface-border">
          {[
            { key: 'critical', label: 'Critical' },
            { key: 'high', label: 'High' },
            { key: 'medium', label: 'Medium' },
            { key: 'low', label: 'Low' },
            { key: 'info', label: 'Informational' },
          ].map(({ key, label }) => <button key={key} type="button" aria-pressed={severityFilter === key} onClick={() => setSeverityFilter(severityFilter === key ? 'all' : key)} className={cn('flex items-center justify-between gap-2 px-3 py-2.5 text-left hover:bg-surface-hover/50 focus-visible:z-10', severityFilter === key && 'bg-accent/5')}>
            <span className={cn('text-[11px] font-medium', getSeverityColor(key).split(' ')[0])}>{label}</span><span className="font-mono text-sm tabular-nums text-text-primary">{severityCounts[key] || 0}</span>
          </button>)}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 border-b border-surface-border py-2.5">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
            <Input
              placeholder="Search title, rule, or file…"
              value={searchQuery}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 text-sm"
            />
          </div>
          <Select
            value={severityFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSeverityFilter(e.target.value)}
            options={severityOptions.map((s) => ({ value: s, label: s === 'all' ? 'All Severities' : s.charAt(0).toUpperCase() + s.slice(1) }))}
            placeholder="All Severities"
            className="w-auto min-w-[130px] h-9 text-sm"
          />
          <Select
            value={categoryFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCategoryFilter(e.target.value)}
            options={categoryOptions.map((c) => ({ value: c, label: c === 'all' ? 'All Categories' : c.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) }))}
            placeholder="All Categories"
            className="w-auto min-w-[155px] h-9 text-sm"
          />
          <Select
            value={statusFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setStatusFilter(e.target.value)}
            options={statusOptions.map((s) => ({ value: s, label: s === 'all' ? 'All Statuses' : s.charAt(0).toUpperCase() + s.slice(1) }))}
            placeholder="All Statuses"
            className="w-auto min-w-[130px] h-9 text-sm"
          />
          <Button variant="ghost" size="sm" onClick={fetchData} disabled={loading}>
            <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <span className="ml-auto w-full text-right text-[11px] text-text-muted sm:w-auto">Showing {filteredFindings.length} of {findingsTotal.toLocaleString()}</span>
      </div>

      {/* Findings List */}
      <section aria-label="Security findings" className="border-b border-surface-border">
          {filteredFindings.length === 0 ? (
            <div className="text-center py-12">
              <Shield className="h-7 w-7 text-text-muted mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-text-primary mb-1">
                {searchQuery || severityFilter !== 'all' || categoryFilter !== 'all' || statusFilter !== 'all'
                  ? 'No matching findings'
                  : 'No security findings'}
              </h3>
              <p className="text-xs text-text-secondary">
                {searchQuery || severityFilter !== 'all' || categoryFilter !== 'all' || statusFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : 'Run a security scan to find potential issues'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[780px] text-left text-sm">
                <thead><tr className="border-b border-surface-border text-[10px] uppercase tracking-[.12em] text-text-muted">
                  <th scope="col" className="py-2.5 pl-3 pr-4 font-semibold">Finding</th><th scope="col" className="px-3 py-2.5 font-semibold">Severity</th><th scope="col" className="px-3 py-2.5 font-semibold">Location</th><th scope="col" className="px-3 py-2.5 font-semibold">Status</th><th scope="col" className="px-3 py-2.5 font-semibold">Updated</th>
                </tr></thead>
                <tbody className="divide-y divide-surface-border/80">
                  {filteredFindings.map((finding) => <tr key={finding.id} className="hover:bg-surface-hover/40">
                    <td className="py-2.5 pl-3 pr-4"><button type="button" onClick={() => { setSelectedFinding(finding); setDetailDrawerOpen(true) }} className="block max-w-full rounded-sm text-left focus-visible:outline-accent" aria-label={`Inspect ${finding.title}`}><span className="block truncate font-medium text-text-primary">{finding.title}</span><span className="mt-0.5 flex items-center gap-2 text-[10px] text-text-muted"><span className="font-mono">{finding.rule_id}</span><span>·</span><span className="capitalize">{finding.category.replace('_', ' ')}</span></span></button></td>
                    <td className="px-3 py-2.5"><Badge variant={finding.severity as any}>{finding.severity}</Badge><span className="ml-1.5 text-[10px] text-text-muted">{finding.confidence} confidence</span></td>
                    <td className="px-3 py-2.5"><span className="block max-w-[280px] truncate font-mono text-[11px] text-text-secondary">{finding.file_path || '—'}</span><span className="text-[10px] text-text-muted">{finding.file_path ? `L${finding.start_line || 1}–L${finding.end_line || '?'}` : 'No file location'}</span></td>
                    <td className="px-3 py-2.5"><Badge variant={finding.status as any}>{finding.status}</Badge></td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-xs text-text-muted">{formatRelativeTime(finding.updated_at)}</td>
                  </tr>)}
                </tbody>
              </table>
            </div>
          )}
      </section>

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
