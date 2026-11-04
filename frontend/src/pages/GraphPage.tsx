import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle, ArrowDownLeft, ArrowUpRight, ChevronLeft,
  FileCode2, FolderTree, GitBranch, Info, Loader2, Maximize2, Minus, Plus,
  RefreshCw, Search, X,
} from 'lucide-react'
import { api } from '../api/client'
import { Badge, Button, Card, Input } from '../components'
import type { DependencyGraphNode, DependencyGraphResponse, DependencyImpactResponse, DependencyNodeDetails, Repository } from '../types'
import { getErrorMessage } from '../utils/format'
import StructuredDependencyGraph, { type StructuredDependencyGraphHandle } from './StructuredDependencyGraph'

type ViewMode = 'overview' | 'files' | 'focus'
type Perspective = 'dependencies' | 'impact'

function IconButton({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
  return <button type="button" title={label} aria-label={label} onClick={onClick} disabled={disabled} className="inline-flex h-8 w-8 items-center justify-center rounded border border-surface-border bg-background-tertiary text-text-secondary transition-colors duration-150 hover:border-accent/50 hover:text-text-primary disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent motion-reduce:transition-none">{children}</button>
}
function makeNode(path: string, known?: DependencyGraphNode): DependencyGraphNode {
  return known || { id: `file:${path}`, type: 'file', label: path.split('/').pop() || path, path, language: 'python', degree: 0, x: 0, y: 0 }
}

export function GraphPage() {
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [repositoryId, setRepositoryId] = useState('')
  const [graph, setGraph] = useState<DependencyGraphResponse | null>(null)
  const [searchGraph, setSearchGraph] = useState<DependencyGraphResponse | null>(null)
  const [focusGraph, setFocusGraph] = useState<DependencyGraphResponse | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [details, setDetails] = useState<DependencyNodeDetails | null>(null)
  const [depth, setDepth] = useState<1 | 2>(1)
  const [perspective, setPerspective] = useState<Perspective>('dependencies')
  const [impact, setImpact] = useState<DependencyImpactResponse | null>(null)
  const [activeDirectory, setActiveDirectory] = useState('.')
  const [mode, setMode] = useState<ViewMode>('overview')
  const [query, setQuery] = useState('')
  const [relationship, setRelationship] = useState('all')
  const [language, setLanguage] = useState('all')
  const graphViewRef = useRef<StructuredDependencyGraphHandle>(null)
  const searchSequence = useRef(0)
  const detailsSequence = useRef(0)
  const impactSequence = useRef(0)
  const fileSelectionSequence = useRef(0)
  const [loadingRepos, setLoadingRepos] = useState(true)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [loadingSearch, setLoadingSearch] = useState(false)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [error, setError] = useState('')
  const [repoError, setRepoError] = useState('')
  const [detailsError, setDetailsError] = useState('')
  const [impactError, setImpactError] = useState('')

  const clearSelection = useCallback(() => {
    setSelectedId(null); setDetails(null); setFocusGraph(null); setImpact(null)
    setDetailsError(''); setImpactError(''); setMode(current => current === 'focus' ? 'files' : current)
  }, [])

  const loadRepositories = useCallback(async () => {
    setLoadingRepos(true); setRepoError('')
    try {
      const response = await api.listRepositories({ limit: 100 })
      const indexed = response.repositories.filter(repository => repository.status === 'indexed')
      setRepositories(indexed)
      setRepositoryId(current => indexed.some(repository => repository.id === current) ? current : indexed[0]?.id || '')
    } catch (err) { setRepoError(getErrorMessage(err, 'Could not load repositories.')) }
    finally { setLoadingRepos(false) }
  }, [])

  const loadGraph = useCallback(async () => {
    if (!repositoryId) { setGraph(null); return }
    setLoadingGraph(true); setError(''); clearSelection(); setMode('overview'); setActiveDirectory('.')
    try { setGraph(await api.getDependencyGraph(repositoryId)) }
    catch (err) { setGraph(null); setError(getErrorMessage(err, 'Could not load dependency graph.')) }
    finally { setLoadingGraph(false) }
  }, [repositoryId, clearSelection])

  useEffect(() => { void loadRepositories() }, [loadRepositories])
  useEffect(() => { if (repositoryId) void loadGraph() }, [repositoryId, loadGraph])

  useEffect(() => {
    if (!repositoryId || !query.trim()) { setSearchGraph(null); setLoadingSearch(false); return }
    const sequence = ++searchSequence.current
    setLoadingSearch(true)
    const timer = window.setTimeout(async () => {
      try {
        const result = await api.getDependencyGraph(repositoryId, { query: query.trim() })
        if (sequence === searchSequence.current) setSearchGraph(result)
      } catch (err) {
        if (sequence === searchSequence.current) { setSearchGraph(null); setError(getErrorMessage(err, 'Search could not reach the repository graph.')) }
      } finally { if (sequence === searchSequence.current) setLoadingSearch(false) }
    }, 240)
    return () => window.clearTimeout(timer)
  }, [repositoryId, query])

  useEffect(() => {
    if (!repositoryId || !selectedId || !focusGraph) { setDetails(null); setLoadingDetails(false); return }
    const sequence = ++detailsSequence.current
    setLoadingDetails(true); setDetailsError(''); setImpact(null)
    void api.getDependencyNode(repositoryId, selectedId, depth).then(result => {
      if (sequence === detailsSequence.current) setDetails(result)
    }).catch(err => {
      if (sequence !== detailsSequence.current) return
      const node = focusGraph.nodes.find(item => item.id === selectedId)
      if (!node) { setDetails(null); setDetailsError(getErrorMessage(err, 'File details are not available.')); return }
      const directDependencies = focusGraph.edges.filter(edge => edge.source === selectedId).map(edge => focusGraph.nodes.find(item => item.id === edge.target)?.path).filter((path): path is string => Boolean(path))
      const directDependents = focusGraph.edges.filter(edge => edge.target === selectedId).map(edge => focusGraph.nodes.find(item => item.id === edge.source)?.path).filter((path): path is string => Boolean(path))
      setDetails({ repository_id: repositoryId, depth: 1, node, direct_dependencies: directDependencies, direct_dependents: directDependents, dependencies: directDependencies, dependents: directDependents, dependency_count: directDependencies.length, dependent_count: directDependents.length })
      setDetailsError('Showing direct relationships from the current graph response; deeper details are unavailable for this search result.')
    }).finally(() => { if (sequence === detailsSequence.current) setLoadingDetails(false) })
  }, [repositoryId, selectedId, depth, focusGraph])

  useEffect(() => {
    if (!repositoryId || !selectedId || perspective !== 'impact') { setImpact(null); setImpactError(''); return }
    const sequence = ++impactSequence.current
    setImpactError('')
    void api.getDependencyImpact(repositoryId, selectedId, depth).then(result => {
      if (sequence === impactSequence.current) setImpact(result)
    }).catch(err => { if (sequence === impactSequence.current) { setImpact(null); setImpactError(getErrorMessage(err, 'Impact analysis is unavailable.')) } })
    return () => { impactSequence.current += 1 }
  }, [repositoryId, selectedId, depth, perspective])

  const baseGraph = graph
  const filteredGraph = useMemo(() => {
    if (!baseGraph) return null
    const nodes = baseGraph.nodes.filter(node => language === 'all' || node.language === language)
    const ids = new Set(nodes.map(node => node.id))
    const edges = relationship === 'files' ? [] : baseGraph.edges.filter(edge => ids.has(edge.source) && ids.has(edge.target) && (relationship === 'all' || edge.type === relationship))
    return { ...baseGraph, nodes, edges }
  }, [baseGraph, language, relationship])
  const activeGraph = mode === 'focus' && focusGraph ? focusGraph : filteredGraph || baseGraph
  const matchingNodes = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase()
    return needle ? (searchGraph?.nodes || []).filter(node => `${node.path} ${node.label}`.toLocaleLowerCase().includes(needle)) : []
  }, [query, searchGraph])
  const impactPaths = useMemo(() => impact?.affected_dependents || [], [impact])

  const openDirectory = (path: string) => { setActiveDirectory(path || '.'); setMode('files'); clearSelection(); window.requestAnimationFrame(() => graphViewRef.current?.fit()) }
  const openOverview = () => { setMode('overview'); setActiveDirectory('.'); clearSelection(); window.requestAnimationFrame(() => graphViewRef.current?.fit()) }
  const selectFile = async (node: DependencyGraphNode, sourceGraph: DependencyGraphResponse | null = activeGraph) => {
    const sequence = ++fileSelectionSequence.current
    let selectedGraph = sourceGraph
    let known = selectedGraph?.nodes.find(item => item.id === node.id || item.path === node.path)
    if (!known && repositoryId) {
      try { selectedGraph = await api.getDependencyGraph(repositoryId, { query: node.path }); known = selectedGraph.nodes.find(item => item.path === node.path) }
      catch { /* Node details can still validate the selected path and report missing data. */ }
      if (sequence !== fileSelectionSequence.current) return
    }
    const actualNode = known || node
    setSelectedId(actualNode.id || `file:${actualNode.path}`)
    setFocusGraph(selectedGraph || graph)
    setDetails(null); setImpact(null); setDetailsError(''); setImpactError('')
    setPerspective('dependencies'); setDepth(1); setMode('focus')
    window.requestAnimationFrame(() => graphViewRef.current?.focus(actualNode.id))
  }
  const selectSearchResult = (node: DependencyGraphNode) => { void selectFile(node, searchGraph) }
  const navigateToPath = (path: string) => {
    const node = focusGraph?.nodes.find(item => item.path === path) || graph?.nodes.find(item => item.path === path) || searchGraph?.nodes.find(item => item.path === path) || makeNode(path)
    void selectFile(node, [searchGraph, focusGraph, graph].find(candidate => candidate?.nodes.some(item => item.path === path)) || graph)
  }
  const setViewMode = (next: 'overview' | 'files') => { clearSelection(); setMode(next); if (next === 'overview') setActiveDirectory('.'); window.requestAnimationFrame(() => graphViewRef.current?.fit()) }
  const resetGraph = () => { setDetailsError(''); graphViewRef.current?.reset() }
  const clearFilters = () => { setRelationship('all'); setLanguage('all') }
  const clearSearch = () => { setQuery(''); setSearchGraph(null); clearSelection() }
  return <div className="space-y-4 animate-in min-w-0">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="mb-1 text-[10px] uppercase tracking-[.15em] text-accent">Explore / Structure</p><h1 className="text-2xl font-semibold tracking-tight text-text-primary">Dependency graph</h1><p className="mt-1 text-xs text-text-secondary">Start with directory relationships, then explore the files behind each connection.</p></div>
      <label className="flex min-w-[220px] flex-col gap-1 text-[10px] uppercase tracking-wide text-text-muted">Repository
        <select aria-label="Repository" value={repositoryId} onChange={event => { clearSelection(); setRepositoryId(event.target.value) }} disabled={loadingRepos || repositories.length === 0} className="h-9 min-w-[220px] rounded-md border border-surface-border bg-background-tertiary px-3 text-xs normal-case tracking-normal text-text-primary outline-none focus:border-accent">
          {repositories.map(repository => <option key={repository.id} value={repository.id}>{repository.display_name}</option>)}
        </select>
      </label>
    </header>

    {repoError && <div role="alert" className="flex items-center justify-between gap-3 rounded-md border border-status-danger/25 bg-status-danger/5 px-3 py-2 text-xs text-text-primary"><span>{repoError}</span><Button variant="secondary" size="sm" onClick={() => void loadRepositories()}>Retry</Button></div>}

    {graph && <section className="flex flex-wrap items-center justify-between gap-2 border-y border-surface-border/80 py-2 text-[10px]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-text-secondary"><span className="inline-flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-accent" />Python imports</span><span className="text-warning">Partial language coverage</span><span><strong className="font-mono text-text-primary">{graph.python_files}</strong> Python files analyzed</span><span><strong className="font-mono text-text-primary">{graph.resolved_relationships}</strong> resolved imports</span>{graph.parse_errors > 0 && <span className="text-warning">{graph.parse_errors} parse issues</span>}</div>
      {graph.truncated && <p role="status" className="text-warning">API display is capped at 250 files and 800 relationships. Search to locate other files.</p>}
    </section>}

    <Card padding="none" className="overflow-hidden">
      <div className="flex flex-col gap-2 border-b border-surface-border px-3 py-2">
       <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div role="group" aria-label="Search and graph filters" className="flex min-w-0 flex-wrap items-center gap-2">
          <div className="relative w-[min(300px,75vw)]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
            <Input aria-label="Search graph files" placeholder="Search files and modules" value={query} onChange={event => setQuery(event.target.value)} className="h-8 pl-8 pr-8 text-xs" />
            {query && <button type="button" title="Clear search" aria-label="Clear search" onClick={clearSearch} className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"><X className="h-3.5 w-3.5" /></button>}
          </div>
          <label className="flex items-center gap-1.5 text-[10px] text-text-muted">Relationships
            <select aria-label="Relationship filter" value={relationship} onChange={event => setRelationship(event.target.value)} className="h-8 rounded-md border border-surface-border bg-background-tertiary px-2 text-xs text-text-secondary outline-none focus:border-accent"><option value="all">All graph data</option><option value="imports">Imports</option><option value="files">Files only</option></select>
          </label>
          <label className="flex items-center gap-1.5 text-[10px] text-text-muted">Language
            <select aria-label="Language" value={language} onChange={event => setLanguage(event.target.value)} className="h-8 rounded-md border border-surface-border bg-background-tertiary px-2 text-xs text-text-secondary outline-none focus:border-accent"><option value="all">All languages</option><option value="python">Python</option></select>
          </label>
          <Button variant="ghost" size="sm" className="h-8 px-2 text-xs" onClick={clearFilters}>Clear filters</Button>
        </div>
        <div role="group" aria-label="Graph views and navigation" className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Graph view" className="flex items-center rounded-md border border-surface-border p-0.5">
            <button type="button" aria-pressed={mode === 'overview'} onClick={() => setViewMode('overview')} className={`inline-flex h-7 items-center gap-1 rounded px-2 text-[10px] transition-colors ${mode === 'overview' ? 'bg-accent/20 text-text-primary' : 'text-text-muted hover:text-text-primary'}`}><FolderTree className="h-3.5 w-3.5" />Overview</button>
            <button type="button" aria-pressed={mode === 'files'} onClick={() => setViewMode('files')} className={`inline-flex h-7 items-center gap-1 rounded px-2 text-[10px] transition-colors ${mode === 'files' ? 'bg-accent/20 text-text-primary' : 'text-text-muted hover:text-text-primary'}`}><FileCode2 className="h-3.5 w-3.5" />Files</button>
          </div>
          {mode === 'files' && <div className="flex items-center gap-1 text-[10px] text-text-muted">{activeDirectory !== '.' && <button type="button" onClick={() => { const parent = activeDirectory.split('/').slice(0, -1).join('/') || '.'; setActiveDirectory(parent); window.requestAnimationFrame(() => graphViewRef.current?.fit()) }} className="inline-flex h-7 items-center gap-1 rounded border border-surface-border px-2 hover:text-text-primary"><ChevronLeft className="h-3 w-3" />Up</button>}<span className="max-w-[140px] truncate font-mono">{activeDirectory}</span></div>}
          {mode === 'focus' && <div role="group" aria-label="Relationship perspective" className="flex items-center rounded-md border border-surface-border p-0.5"><button type="button" aria-pressed={perspective === 'dependencies'} onClick={() => setPerspective('dependencies')} className={`h-7 rounded px-2 text-[10px] ${perspective === 'dependencies' ? 'bg-accent/20 text-text-primary' : 'text-text-muted'}`}>Dependencies</button><button type="button" aria-pressed={perspective === 'impact'} onClick={() => setPerspective('impact')} className={`h-7 rounded px-2 text-[10px] ${perspective === 'impact' ? 'bg-accent/20 text-text-primary' : 'text-text-muted'}`}>Impact</button></div>}
          {mode === 'focus' && <label className="flex items-center gap-1 text-[10px] text-text-muted">Depth<select aria-label="Dependency depth" value={depth} onChange={event => setDepth(Number(event.target.value) as 1 | 2)} className="h-8 rounded-md border border-surface-border bg-background-tertiary px-2 text-xs text-text-secondary outline-none focus:border-accent"><option value={1}>Direct · 1</option><option value={2}>Two levels · 2</option></select></label>}
          <span className="mx-0.5 hidden h-5 border-l border-surface-border sm:block" />
          <IconButton label="Zoom out" onClick={() => graphViewRef.current?.zoomBy(.82)}><Minus className="h-3.5 w-3.5" /></IconButton><IconButton label="Zoom in" onClick={() => graphViewRef.current?.zoomBy(1.22)}><Plus className="h-3.5 w-3.5" /></IconButton><IconButton label="Fit graph to screen" onClick={() => graphViewRef.current?.fit()}><Maximize2 className="h-3.5 w-3.5" /></IconButton><IconButton label="Reset graph layout" onClick={resetGraph}><RefreshCw className="h-3.5 w-3.5" /></IconButton>
          {mode === 'focus' && <IconButton label="Close focused file" onClick={clearSelection}><X className="h-3.5 w-3.5" /></IconButton>}
        </div>
       </div>
      </div>

      {query.trim() && <div className="flex flex-wrap items-center gap-2 border-b border-surface-border bg-background/60 px-3 py-2" aria-label="Graph search results"><span className="text-[10px] uppercase tracking-wide text-text-muted">{loadingSearch ? 'Searching' : 'Matches'}</span>{loadingSearch && <Loader2 className="h-3 w-3 animate-spin text-accent motion-reduce:animate-none" />}{matchingNodes.slice(0, 8).map(node => <button type="button" key={node.id} title={node.path} aria-pressed={selectedId === node.id} onClick={() => selectSearchResult(node)} className={`max-w-full truncate rounded border px-2 py-1 font-mono text-[10px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${selectedId === node.id ? 'border-accent bg-accent/15 text-text-primary' : 'border-surface-border text-text-secondary hover:border-accent/50 hover:text-text-primary'}`}>{node.path}</button>)}{matchingNodes.length > 8 && <span className="text-[10px] text-text-muted">+{matchingNodes.length - 8} more matches in API result</span>}{!loadingSearch && matchingNodes.length === 0 && searchGraph && <span className="text-[10px] text-text-muted">No matching files.</span>}</div>}

      <div className="relative h-[min(68vh,720px)] min-h-[460px] sm:min-h-[540px]">
        {loadingGraph && <div className="absolute inset-0 z-10 grid place-items-center bg-background/75" role="status"><span className="flex items-center gap-2 rounded-md border border-surface-border bg-surface px-3 py-2 text-xs text-text-secondary"><Loader2 className="h-4 w-4 animate-spin text-accent motion-reduce:animate-none" />Loading repository graph…</span></div>}
        {activeGraph && activeGraph.nodes.length > 0 && !loadingGraph && mode !== 'focus' && activeGraph.resolved_relationships === 0 && <div className="absolute inset-0 z-10 grid place-items-center bg-background/75 p-6 text-center"><div><FileCode2 className="mx-auto h-8 w-8 text-text-muted" /><h2 className="mt-3 text-sm font-semibold text-text-primary">No internal imports detected</h2><p className="mt-1 max-w-md text-xs text-text-secondary">{activeGraph.python_files ? `Analyzed ${activeGraph.python_files} Python files, but found no repository-internal import relationships.` : 'This repository has no supported Python source files. The graph covers Python imports only.'}</p></div></div>}
        {activeGraph && activeGraph.nodes.length > 0 && !loadingGraph && (mode !== 'focus' || focusGraph) && <StructuredDependencyGraph ref={graphViewRef} graph={activeGraph} mode={mode} activeDirectory={activeDirectory} selectedId={selectedId} details={details} depth={depth} perspective={perspective} impactPaths={impactPaths} onOpenDirectory={openDirectory} onSelectFile={node => { void selectFile(node, mode === 'focus' ? focusGraph : activeGraph) }} />}
        {!loadingRepos && !repoError && repositories.length === 0 && <div className="absolute inset-0 grid place-items-center p-6 text-center"><div><GitBranch className="mx-auto h-8 w-8 text-text-muted" /><h2 className="mt-3 text-sm font-semibold text-text-primary">No indexed repositories</h2><p className="mt-1 max-w-sm text-xs leading-relaxed text-text-secondary">Index a repository first. The graph is built from source files and shows only resolved relationships.</p></div></div>}
        {activeGraph && activeGraph.nodes.length === 0 && !loadingGraph && <div className="absolute inset-0 grid place-items-center p-6 text-center"><div><Search className="mx-auto h-7 w-7 text-text-muted" /><h2 className="mt-2 text-sm font-medium text-text-primary">No files in this view</h2><p className="mt-1 text-xs text-text-secondary">Clear filters or return to the repository overview.</p><Button variant="ghost" size="sm" className="mt-1" onClick={() => { clearFilters(); setViewMode('overview') }}>Clear filters</Button></div></div>}
        {(error || (repoError && !repositories.length)) && <div role="alert" className="absolute inset-0 z-20 grid place-items-center bg-background/90 p-6 text-center"><div><AlertCircle className="mx-auto h-7 w-7 text-status-danger" /><p className="mt-2 max-w-md text-sm text-text-primary">{error || repoError}</p><Button variant="secondary" size="sm" className="mt-3" onClick={() => { setError(''); if (repositories.length) void loadGraph(); else void loadRepositories() }}>Retry</Button></div></div>}

        {mode === 'focus' && selectedId && (loadingDetails || detailsError || impactError) && <div role={loadingDetails ? 'status' : 'alert'} className="absolute left-3 top-3 z-10 flex max-w-[min(500px,calc(100%-24px))] items-center gap-2 rounded border border-surface-border bg-surface/95 px-3 py-2 text-[10px] text-text-secondary shadow-lg">{loadingDetails && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-accent motion-reduce:animate-none" />}{detailsError || impactError || 'Loading file details…'}</div>}
        {mode === 'focus' && perspective === 'impact' && !impact && !impactError && !loadingDetails && <div role="status" className="absolute left-3 top-3 z-10 rounded border border-surface-border bg-surface/95 px-3 py-2 text-[10px] text-text-muted">Loading affected files…</div>}

        {mode === 'focus' && selectedId && details && <aside aria-label="Selected file details" className="absolute inset-x-2 bottom-2 top-2 z-10 flex flex-col border border-surface-border bg-surface/95 shadow-xl backdrop-blur-sm transition-transform duration-200 motion-reduce:transition-none lg:inset-y-3 lg:left-auto lg:right-3 lg:w-[304px]">
          <div className="flex items-start gap-2 border-b border-surface-border p-3"><div className="min-w-0 flex-1"><Badge variant="info" size="sm">{details.node.language}</Badge><h2 className="mt-2 break-all font-mono text-xs font-semibold text-text-primary">{details.node.path}</h2><p className="mt-1 text-[10px] text-text-muted">{details.dependency_count} direct imports · {details.dependent_count} direct dependents</p></div><IconButton label="Close node details" onClick={clearSelection}><X className="h-4 w-4" /></IconButton></div>
          <div className="flex-1 space-y-4 overflow-y-auto p-3 text-xs">
            <section><h3 className="mb-2 flex items-center gap-1.5 font-medium text-text-secondary"><ArrowUpRight className="h-3.5 w-3.5 text-accent" />Imports ({details.direct_dependencies.length})</h3>{details.direct_dependencies.length ? <ul className="space-y-1.5">{details.direct_dependencies.map(path => <li key={path}><button type="button" onClick={() => navigateToPath(path)} title={path} className="w-full break-all rounded border border-surface-border/70 px-2 py-1.5 text-left font-mono text-[10px] text-text-primary hover:border-accent/50 hover:bg-accent/5">{path}</button></li>)}</ul> : <p className="text-[11px] text-text-muted">No resolved internal imports.</p>}</section>
            <section><h3 className="mb-2 flex items-center gap-1.5 font-medium text-text-secondary"><ArrowDownLeft className="h-3.5 w-3.5 text-cyan-300" />Imported by ({details.direct_dependents.length})</h3>{details.direct_dependents.length ? <ul className="space-y-1.5">{details.direct_dependents.map(path => <li key={path}><button type="button" onClick={() => navigateToPath(path)} title={path} className="w-full break-all rounded border border-surface-border/70 px-2 py-1.5 text-left font-mono text-[10px] text-text-primary hover:border-accent/50 hover:bg-accent/5">{path}</button></li>)}</ul> : <p className="text-[11px] text-text-muted">No resolved dependents.</p>}</section>
            {depth === 2 && <section className="border-t border-surface-border pt-3"><h3 className="font-medium text-text-secondary">Two-level reachability</h3><p className="mt-1 text-[10px] leading-relaxed text-text-muted">{details.dependencies.length} dependency files · {details.dependents.length} dependent files. The API does not provide intermediate edges for this depth.</p></section>}
            {perspective === 'impact' && impact && <section className="border-t border-surface-border pt-3"><h3 className="font-medium text-text-secondary">Impact scope</h3><p className="mt-1 text-[11px] text-text-muted">{impact.affected_dependents.length} affected files through depth {impact.depth}</p></section>}
          </div>
          <div className="border-t border-surface-border p-3"><Button variant={perspective === 'impact' ? 'primary' : 'secondary'} size="sm" className="w-full" onClick={() => setPerspective(current => current === 'impact' ? 'dependencies' : 'impact')}>{perspective === 'impact' ? 'Return to dependencies' : 'Show impact view'}</Button></div>
        </aside>}
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-surface-border px-3 py-2 text-[10px] text-text-muted"><span className="inline-flex items-center gap-1.5"><Info className="h-3 w-3 text-accent" />Only resolved, repository-internal Python imports are shown; external packages and other languages are not represented.</span>{graph?.truncated && <span>Display cap: 250 files / 800 relationships</span>}</footer>
    </Card>
  </div>
}
