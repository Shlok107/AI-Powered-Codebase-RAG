import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import type { DependencyGraphEdge, DependencyGraphNode, DependencyGraphResponse, DependencyNodeDetails } from '../types'
import { CARD_GAP_X, CARD_WIDTH, cardHeight, findOverlappingCards, fitGraphTransform, layoutFocusGraph, layoutLayeredGraph, type GraphDirection, type GraphLayout, type GraphLayoutEdge, type GraphLayoutItem } from './graphLayout'

type ViewMode = 'overview' | 'files' | 'focus'
type Perspective = 'dependencies' | 'impact'
type Point = { x: number; y: number }
type GraphItem = GraphLayoutItem & { fileCount?: number; importCount?: number; language?: string }
type AggregatedEdge = GraphLayoutEdge
type DirectoryGraph = GraphLayout
type Transform = { x: number; y: number; scale: number }

const ROOT_ID = 'directory:.'

export interface StructuredDependencyGraphHandle {
  zoomBy: (factor: number) => void
  fit: () => void
  reset: () => void
  focus: (id: string) => void
}

interface Props {
  graph: DependencyGraphResponse
  mode: ViewMode
  activeDirectory: string
  selectedId: string | null
  details: DependencyNodeDetails | null
  depth: 1 | 2
  perspective: Perspective
  impactPaths: string[]
  onOpenDirectory: (path: string) => void
  onSelectFile: (node: DependencyGraphNode) => void
}

function parentPath(path: string) { const parts = path.split('/'); parts.pop(); return parts.join('/') }
function basename(path: string) { return path.split('/').pop() || path }
function normalizedPath(path: string) { return path.replace(/\\/g, '/').replace(/^\.\//, '') }

function directoryMembership(path: string, directoryDepth = 1) {
  const parts = normalizedPath(path).split('/').filter(Boolean)
  if (parts.length <= 1) return ROOT_ID
  return `directory:${parts.slice(0, Math.min(directoryDepth, parts.length - 1)).join('/')}`
}

function layoutItems(items: GraphItem[], edges: AggregatedEdge[]): DirectoryGraph {
  return layoutLayeredGraph(items, edges)
}

function aggregateForGroups(graph: DependencyGraphResponse, groupForPath: (path: string) => string) {
  const items = new Map<string, GraphItem>()
  graph.nodes.forEach(node => {
    const id = groupForPath(node.path)
    if (!items.has(id)) {
      const path = id === ROOT_ID ? '.' : id.replace(/^directory:/, '')
      items.set(id, { id, kind: 'directory', label: id === ROOT_ID ? 'Repository root' : `${basename(path)}/`, path, fileCount: 0, importCount: 0 })
    }
    items.get(id)!.fileCount = (items.get(id)!.fileCount || 0) + 1
  })
  const pairs = new Map<string, AggregatedEdge>()
  const seenFilePairs = new Set<string>()
  graph.edges.forEach(edge => {
    const sourceNode = graph.nodes.find(node => node.id === edge.source)
    const targetNode = graph.nodes.find(node => node.id === edge.target)
    if (!sourceNode || !targetNode) return
    const filePair = `${sourceNode.path}\u0000${targetNode.path}`
    if (seenFilePairs.has(filePair)) return
    seenFilePairs.add(filePair)
    const source = groupForPath(sourceNode.path), target = groupForPath(targetNode.path)
    if (source === target) { const group = items.get(source); if (group) group.importCount = (group.importCount || 0) + 1; return }
    const key = `${source}\u0000${target}`
    const entry = pairs.get(key) || { source, target, count: 0 }
    entry.count += 1; pairs.set(key, entry)
  })
  return { items: [...items.values()], edges: [...pairs.values()] }
}

function buildOverview(graph: DependencyGraphResponse): DirectoryGraph {
  const groups = aggregateForGroups(graph, path => directoryMembership(path, 1))
  return layoutItems(groups.items, groups.edges)
}

function buildDirectoryView(graph: DependencyGraphResponse, directory: string): DirectoryGraph {
  const prefix = directory === '.' ? '' : `${directory}/`
  const items = new Map<string, GraphItem>()
  const fileItemByPath = new Map<string, string>()
  graph.nodes.forEach(file => {
    const normalized = normalizedPath(file.path)
    if (prefix && !normalized.startsWith(prefix)) return
    const rest = prefix ? normalized.slice(prefix.length) : normalized
    if (!rest) return
    const segments = rest.split('/')
    if (segments.length === 1) {
      const id = file.id
      items.set(id, { id, kind: 'file', label: basename(file.path), path: file.path, fileCount: 1, importCount: 0, language: file.language, file })
      fileItemByPath.set(file.path, id)
    } else {
      const childPath = directory === '.' ? segments[0] : `${directory}/${segments[0]}`
      const id = `directory:${childPath}`
      if (!items.has(id)) items.set(id, { id, kind: 'directory', label: `${segments[0]}/`, path: childPath, fileCount: 0, importCount: 0 })
      items.get(id)!.fileCount = (items.get(id)!.fileCount || 0) + 1
      fileItemByPath.set(file.path, id)
    }
  })
  const pairs = new Map<string, AggregatedEdge>(), seen = new Set<string>()
  graph.edges.forEach(edge => {
    const source = graph.nodes.find(node => node.id === edge.source), target = graph.nodes.find(node => node.id === edge.target)
    if (!source || !target || !fileItemByPath.has(source.path) || !fileItemByPath.has(target.path)) return
    const filePair = `${source.path}\u0000${target.path}`
    if (seen.has(filePair)) return
    seen.add(filePair)
    const from = fileItemByPath.get(source.path)!, to = fileItemByPath.get(target.path)!
    if (from === to) { const item = items.get(from); if (item?.kind === 'directory') item.importCount = (item.importCount || 0) + 1; return }
    const key = `${from}\u0000${to}`, entry = pairs.get(key) || { source: from, target: to, count: 0 }
    entry.count += 1; pairs.set(key, entry)
  })
  return layoutItems([...items.values()], [...pairs.values()])
}

function makeNode(path: string, known?: DependencyGraphNode): DependencyGraphNode {
  return known || { id: `file:${path}`, type: 'file', label: basename(path), path, language: 'python', degree: 0, x: 0, y: 0 }
}

type FocusNode = GraphItem & { direction: GraphDirection }
function buildFocus(details: DependencyNodeDetails | null, graph: DependencyGraphResponse, selectedId: string | null, depth: 1 | 2, perspective: Perspective, impactPaths: string[]): DirectoryGraph & { focusNodes: FocusNode[] } {
  const selected = graph.nodes.find(node => node.id === selectedId) || details?.node
  if (!selected) return { items: [], edges: [], width: 1200, height: 740, focusNodes: [] }
  const directDeps = details?.direct_dependencies || graph.edges.filter(edge => edge.source === selected.id).map(edge => graph.nodes.find(node => node.id === edge.target)?.path).filter((path): path is string => Boolean(path))
  const directDependents = details?.direct_dependents || graph.edges.filter(edge => edge.target === selected.id).map(edge => graph.nodes.find(node => node.id === edge.source)?.path).filter((path): path is string => Boolean(path))
  const dependencies = depth === 2 ? details?.dependencies || directDeps : directDeps
  const dependents = depth === 2 ? (perspective === 'impact' && impactPaths.length ? impactPaths : details?.dependents || directDependents) : directDependents
  const dependencySet = new Set(directDeps), dependentSet = new Set(directDependents)
  const candidates: FocusNode[] = [{ id: selected.id, kind: 'file', label: basename(selected.path), path: selected.path, fileCount: 1, importCount: 0, file: selected, direction: 'root', relationshipLabel: `${directDeps.length} direct imports · ${directDependents.length} importers` }]
  if (perspective === 'dependencies') {
    dependencies.forEach(path => { const direction = dependencySet.has(path) ? 'dependency' : 'transitive-dependency'; candidates.push({ ...makeNode(path, graph.nodes.find(node => node.path === path)), id: `file:${path}`, kind: 'file', label: basename(path), path, fileCount: 1, importCount: 0, direction, relationshipLabel: direction === 'dependency' ? 'Imported by selected file' : 'Reachable within 2 imports · path omitted' }) })
    dependents.forEach(path => { const direction = dependentSet.has(path) ? 'dependent' : 'transitive-dependent'; candidates.push({ ...makeNode(path, graph.nodes.find(node => node.path === path)), id: `file:${path}`, kind: 'file', label: basename(path), path, fileCount: 1, importCount: 0, direction, relationshipLabel: direction === 'dependent' ? 'Imports selected file' : 'Can reach selected · within 2 imports' }) })
  } else {
    const availableDependents = depth === 2 ? (impactPaths.length ? impactPaths : dependents) : directDependents
    availableDependents.forEach(path => { const direction = dependentSet.has(path) ? 'dependent' : 'transitive-dependent'; candidates.push({ ...makeNode(path, graph.nodes.find(node => node.path === path)), id: `file:${path}`, kind: 'file', label: basename(path), path, fileCount: 1, importCount: 0, direction, relationshipLabel: direction === 'dependent' ? 'Imports selected file' : 'Can reach selected · within 2 imports' }) })
  }
  // Transitive results may contain the selected file again through a cycle.
  // Keep the root role so it cannot be overwritten by a neighboring path.
  const unique = [...new Map(candidates.filter(node => node.direction === 'root' || node.path !== selected.path).map(node => [node.id, node])).values()]
  // Direct lists are returned by the node details endpoint and remain authoritative
  // even when the capped overview response omitted a corresponding edge.
  const edges: AggregatedEdge[] = [
    ...directDeps.map(path => ({ source: selected.id, target: `file:${path}`, count: 1 })),
    ...directDependents.map(path => ({ source: `file:${path}`, target: selected.id, count: 1 })),
  ]
  const layout = layoutFocusGraph(unique, edges)
  return { ...layout, focusNodes: layout.items as FocusNode[] }
}

const StructuredDependencyGraph = forwardRef<StructuredDependencyGraphHandle, Props>(function StructuredDependencyGraph(props, ref) {
  const { graph, mode, activeDirectory, selectedId, details, depth, perspective, impactPaths, onOpenDirectory, onSelectFile } = props
  const svgRef = useRef<SVGSVGElement>(null)
  const viewportRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 1200, height: 740 })
  const [transform, setTransform] = useState<Transform>({ x: 0, y: 0, scale: 1 })
  const [positions, setPositions] = useState<Record<string, Point>>({})
  const gestureRef = useRef<{ kind: 'pan' | 'node'; id?: string; x: number; y: number; moved: boolean } | null>(null)
  const pointerRef = useRef<Point>({ x: 0, y: 0 })

  const overview = useMemo(() => buildOverview(graph), [graph])
  const directoryView = useMemo(() => buildDirectoryView(graph, activeDirectory), [graph, activeDirectory])
  const focus = useMemo(() => buildFocus(details, graph, selectedId, depth, perspective, impactPaths), [details, graph, selectedId, depth, perspective, impactPaths])
  const current = mode === 'overview' ? overview : mode === 'files' ? directoryView : focus
  const items = useMemo(() => current.items.map(item => ({ ...item, ...(positions[item.id] || {}) })), [current.items, positions])
  const itemMap = useMemo(() => new Map(items.map(item => [item.id, item])), [items])
  const bounds = useMemo(() => {
    if (!items.length) return { left: 0, top: 0, width: current.width, height: current.height }
    const left = Math.min(0, ...items.map(item => item.x || 0)), top = Math.min(0, ...items.map(item => item.y || 0))
    const right = Math.max(current.width, ...items.map(item => (item.x || 0) + CARD_WIDTH))
    const bottom = Math.max(current.height, ...items.map(item => (item.y || 0) + (item.height || cardHeight(item))))
    return { left, top, width: right - left, height: bottom - top }
  }, [current.width, current.height, items])
  const layoutKey = `${mode}:${activeDirectory}:${selectedId || ''}:${depth}:${perspective}:${graph.repository_id}:${current.items.map(item => item.id).join('|')}:${current.edges.map(edge => `${edge.source}>${edge.target}`).join('|')}`

  const fit = () => {
    const panelWidth = mode === 'focus' && selectedId && window.innerWidth >= 1024 ? 324 : 0
    const next = fitGraphTransform(size.width, size.height, bounds.width, bounds.height, panelWidth)
    setTransform({ ...next, x: next.x - bounds.left * next.scale, y: next.y - bounds.top * next.scale })
  }
  const reset = () => { setPositions({}); window.requestAnimationFrame(fit) }
  const focusId = (id: string) => {
    const node = itemMap.get(id)
    if (!node) return
    const scale = Math.max(.75, transform.scale)
    const panelWidth = mode === 'focus' && selectedId && window.innerWidth >= 1024 ? 324 : 0
    const availableWidth = Math.max(320, size.width - panelWidth)
    const height = node.height || cardHeight(node)
    setTransform({ scale, x: availableWidth / 2 - ((node.x || 0) + CARD_WIDTH / 2) * scale, y: size.height / 2 - ((node.y || 0) + height / 2) * scale })
  }
  useImperativeHandle(ref, () => ({
    zoomBy: factor => setTransform(value => ({ ...value, scale: Math.min(2.5, Math.max(.12, value.scale * factor)) })),
    fit, reset, focus: focusId,
  }))

  useEffect(() => {
    const element = viewportRef.current
    if (!element) return
    const measure = () => { const rect = element.getBoundingClientRect(); if (rect.width && rect.height) setSize({ width: rect.width, height: rect.height }) }
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    observer?.observe(element); window.addEventListener('resize', measure); measure()
    return () => { observer?.disconnect(); window.removeEventListener('resize', measure) }
  }, [])
  useEffect(() => { setPositions({}); window.requestAnimationFrame(fit) // reset the viewport when a new directory, mode or selection is opened
    // fit() uses the current memoized layout through this effect's render closure.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layoutKey])

  useEffect(() => {
    const frame = window.requestAnimationFrame(fit)
    return () => window.cancelAnimationFrame(frame)
    // ResizeObserver changes the available canvas dimensions; preserve a fit view after resizing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size.width, size.height])

  const pointerPoint = (event: { clientX: number; clientY: number }) => {
    const svg = svgRef.current
    const matrix = svg?.getScreenCTM?.()
    if (svg && matrix) {
      const point = svg.createSVGPoint()
      point.x = event.clientX; point.y = event.clientY
      const local = point.matrixTransform(matrix.inverse())
      return { x: local.x, y: local.y }
    }
    const rect = svg?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    return { x: (event.clientX - rect.left) * size.width / (rect.width || size.width), y: (event.clientY - rect.top) * size.height / (rect.height || size.height) }
  }
  const pointerDown = (event: React.PointerEvent<Element>, id?: string) => {
    event.stopPropagation(); svgRef.current?.setPointerCapture?.(event.pointerId)
    const point = pointerPoint(event)
    gestureRef.current = { kind: id ? 'node' : 'pan', id, x: point.x, y: point.y, moved: false }; pointerRef.current = point
  }
  const pointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const gesture = gestureRef.current
    if (!gesture) return
    const point = pointerPoint(event)
    if (Math.hypot(point.x - gesture.x, point.y - gesture.y) > 3) gesture.moved = true
    const dx = point.x - pointerRef.current.x, dy = point.y - pointerRef.current.y
    if (gesture.kind === 'pan') setTransform(value => ({ ...value, x: value.x + dx, y: value.y + dy }))
    else if (gesture.id) {
      const worldX = (point.x - transform.x) / transform.scale, worldY = (point.y - transform.y) / transform.scale
      const active = itemMap.get(gesture.id)
      if (active) {
        const next = { ...active, x: worldX - CARD_WIDTH / 2, y: worldY - (active.height || cardHeight(active)) / 2 }
        const candidate = items.map(item => item.id === gesture.id ? next : item)
        if (!findOverlappingCards(candidate, 8).length) setPositions(value => ({ ...value, [gesture.id!]: { x: next.x!, y: next.y! } }))
      }
    }
    pointerRef.current = point
  }
  const pointerUp = (event: React.PointerEvent<SVGSVGElement>) => {
    const gesture = gestureRef.current
    if (gesture?.kind === 'node' && gesture.id && !gesture.moved) {
      const item = itemMap.get(gesture.id)
      if (item?.kind === 'directory') onOpenDirectory(item.path)
      else if (item?.file) onSelectFile(item.file)
    }
    gestureRef.current = null
    try { event.currentTarget.releasePointerCapture(event.pointerId) } catch { /* capture can be released by pointercancel */ }
  }
  const wheel = (event: React.WheelEvent<SVGSVGElement>) => {
    event.preventDefault()
    const point = pointerPoint(event)
    setTransform(value => {
      const scale = Math.min(2.5, Math.max(.12, value.scale * Math.exp(-event.deltaY * .001)))
      const worldX = (point.x - value.x) / value.scale, worldY = (point.y - value.y) / value.scale
      return { scale, x: point.x - worldX * scale, y: point.y - worldY * scale }
    })
  }

  const edgePath = (edge: AggregatedEdge) => {
    const from = itemMap.get(edge.source), to = itemMap.get(edge.target)
    if (!from || !to) return null
    const fromHeight = from.height || cardHeight(from), toHeight = to.height || cardHeight(to)
    const fromX = from.x || 0, toX = to.x || 0
    const y1 = (from.y || 0) + fromHeight / 2, y2 = (to.y || 0) + toHeight / 2
    if (toX <= fromX) {
      // Back-edges and cyclic links travel around the outside of their columns.
      const laneX = Math.min(fromX, toX) - 30
      return { d: `M ${fromX} ${y1} C ${laneX} ${y1}, ${laneX} ${y2}, ${toX} ${y2}`, x: laneX, y: (y1 + y2) / 2 }
    }
    const x1 = fromX + CARD_WIDTH, x2 = toX
    const bend = Math.max(42, Math.abs(x2 - x1) * .46)
    return { d: `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`, x: (x1 + x2) / 2, y: (y1 + y2) / 2 }
  }

  const directDependents = (focus.focusNodes || []).filter(node => node.direction === 'dependent')
  const directDependencies = (focus.focusNodes || []).filter(node => node.direction === 'dependency')
  const transitiveDependents = (focus.focusNodes || []).filter(node => node.direction === 'transitive-dependent')
  const transitiveDependencies = (focus.focusNodes || []).filter(node => node.direction === 'transitive-dependency')
  const focusRoot = (focus.focusNodes || []).find(node => node.direction === 'root')
  const incomingHeadingX = (directDependents[0]?.x ?? ((focusRoot?.x || 0) - CARD_WIDTH - CARD_GAP_X))
  const outgoingHeadingX = (directDependencies[0]?.x ?? ((focusRoot?.x || 0) + CARD_WIDTH + CARD_GAP_X))

  return <div ref={viewportRef} className="relative h-full min-h-[420px] w-full overflow-hidden bg-background/65">
    <svg ref={svgRef} viewBox={`0 0 ${size.width} ${size.height}`} role="img" aria-label={mode === 'overview' ? 'Repository directory dependency overview' : mode === 'files' ? `Files and imports in ${activeDirectory}` : `Focused dependency graph for ${focusRoot?.path || 'selected file'}`} className="absolute inset-0 h-full w-full touch-none select-none" onPointerDown={event => pointerDown(event)} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp} onWheel={wheel}>
      <defs>
        <marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L7,3 z" fill="#8f7af4" /></marker>
        <marker id="graph-arrow-in" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L7,3 z" fill="#48C8DD" /></marker>
      </defs>
      <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.scale})`}>
        {mode !== 'focus' && current.edges.map((edge, index) => {
          const path = edgePath(edge); if (!path) return null
          return <g key={`${edge.source}:${edge.target}:${index}`} className="pointer-events-none">
            <path d={path.d} fill="none" stroke="#8f7af4" strokeOpacity=".36" strokeWidth="1.5" markerEnd="url(#graph-arrow)" />
            {edge.count > 1 && <g><rect x={path.x - 18} y={path.y - 10} width="36" height="18" rx="8" fill="#17172d" stroke="#565078" /><text x={path.x} y={path.y + 4} textAnchor="middle" fill="#c9c1e6" fontSize="10">{edge.count}</text></g>}
          </g>
        })}
        {mode === 'focus' && current.edges.map((edge, index) => {
          const from = itemMap.get(edge.source), to = itemMap.get(edge.target)
          if (!from || !to) return null
          const incoming = edge.target === selectedId
          const fromHeight = from.height || cardHeight(from), toHeight = to.height || cardHeight(to)
          const forward = (to.x || 0) >= (from.x || 0)
          const x1 = (from.x || 0) + (forward ? CARD_WIDTH : 0), y1 = (from.y || 0) + fromHeight / 2
          const x2 = (to.x || 0) + (forward ? 0 : CARD_WIDTH), y2 = (to.y || 0) + toHeight / 2
          const bend = Math.max(42, Math.abs(x2 - x1) * .46)
          return <path key={`${edge.source}:${edge.target}:${index}`} d={`M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`} fill="none" stroke={incoming ? '#48C8DD' : '#A58AFF'} strokeWidth="2.2" strokeOpacity=".88" markerEnd={incoming ? 'url(#graph-arrow-in)' : 'url(#graph-arrow)'} />
        })}

        {mode === 'focus' && <g className="pointer-events-none">
          {directDependents.length > 0 && <text x={incomingHeadingX} y="34" fill="#68d2e1" fontSize="12" fontWeight="600">FILES THAT IMPORT THIS · {directDependents.length}</text>}
          {directDependencies.length > 0 && <text x={outgoingHeadingX} y="34" fill="#c3b1ff" fontSize="12" fontWeight="600">SELECTED FILE IMPORTS · {directDependencies.length}</text>}
          {focusRoot && <text x={focusRoot.x} y="34" fill="#e5ddff" fontSize="12" fontWeight="700">SELECTED FILE</text>}
          {transitiveDependents.length > 0 && <text x={transitiveDependents[0].x} y="50" fill="#83b9c2" fontSize="10">INDIRECT IMPORTERS · {transitiveDependents.length}</text>}
          {transitiveDependencies.length > 0 && <text x={transitiveDependencies[0].x} y="50" fill="#ad9ce1" fontSize="10">INDIRECT IMPORTS · {transitiveDependencies.length}</text>}
        </g>}
        {mode === 'focus' && current.items.filter(item => item.id !== selectedId).map(item => <GraphCard key={item.id} item={item} selected={false} focusNeighbor={true} onPointerDown={event => pointerDown(event, item.id)} onDoubleClick={() => item.file && onSelectFile(item.file)} />)}
        {mode === 'focus' && focusRoot && <GraphCard item={focusRoot} selected={true} focusNeighbor={false} onPointerDown={event => pointerDown(event, focusRoot.id)} onDoubleClick={() => {}} />}
        {mode !== 'focus' && current.items.map(item => <GraphCard key={item.id} item={item} selected={item.id === selectedId} focusNeighbor={false} onPointerDown={event => pointerDown(event, item.id)} onDoubleClick={() => item.kind === 'directory' ? onOpenDirectory(item.path) : item.file && onSelectFile(item.file)} />)}
      </g>
    </svg>
    {mode === 'files' && <div className="absolute left-3 top-3 rounded border border-surface-border bg-background/90 px-2.5 py-1.5 font-mono text-[10px] text-text-muted">/{activeDirectory === '.' ? '' : `${activeDirectory}/`}</div>}
    <div className="pointer-events-none absolute bottom-3 right-3 rounded border border-surface-border bg-background/90 px-2.5 py-1.5 text-[10px] text-text-muted">Drag nodes to reposition · drag canvas to pan · scroll to zoom</div>
    {mode === 'focus' && depth === 2 && (transitiveDependents.length > 24 || transitiveDependencies.length > 24) && <div className="absolute bottom-3 left-3 rounded border border-warning/30 bg-background/90 px-2 py-1 text-[10px] text-warning">Showing first 24 transitive files per direction.</div>}
  </div>
})

function GraphCard({ item, selected, focusNeighbor, onPointerDown, onDoubleClick }: { item: GraphItem; selected: boolean; focusNeighbor: boolean; onPointerDown: (event: React.PointerEvent<SVGGElement>) => void; onDoubleClick: () => void }) {
  const x = item.x || 0, y = item.y || 0
  const directory = item.kind === 'directory'
  const height = item.height || cardHeight(item)
  const title = item.label.length > 36 ? `${item.label.slice(0, 33)}…` : item.label
  const pathLines = splitPath(item.path)
  const metadata = directory ? `${item.importCount || 0} internal imports` : item.relationshipLabel || (item.file?.degree ? `${item.file.degree} connected files` : 'No resolved internal relationships')
  const pathStart = 50
  const metadataY = height - 16
  return <g transform={`translate(${x} ${y})`} onPointerDown={onPointerDown} onDoubleClick={onDoubleClick} role="button" tabIndex={0} aria-label={`${item.path}; ${directory ? `${item.fileCount || 0} Python files; ${item.importCount || 0} internal imports` : metadata}`} className="cursor-grab outline-none active:cursor-grabbing" onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onDoubleClick() } }}>
    <title>{`${item.path} · ${directory ? `${item.fileCount || 0} Python files · ${item.importCount || 0} internal imports` : metadata}`}</title>
    {selected && <rect x="-4" y="-4" width={CARD_WIDTH + 8} height={height + 8} rx="12" fill="none" stroke="#a58aff" strokeOpacity=".5" strokeWidth="2" />}
    <rect width={CARD_WIDTH} height={height} rx="9" fill={directory ? '#252344' : selected ? '#342b58' : '#1d1d36'} stroke={selected ? '#A58AFF' : directory ? '#59527e' : focusNeighbor ? '#554d78' : '#36344f'} strokeWidth={selected ? 2 : 1.2} />
    <rect x="0" y="0" width="4" height={height} rx="2" fill={selected ? '#A58AFF' : directory ? '#7661d5' : focusNeighbor ? '#48C8DD' : '#514b70'} />
    {directory ? <>
      <text x="14" y="27" fill="#f2efff" fontSize="14" fontWeight="600">{title}</text>
      {pathLines.map((line, index) => <text key={index} x="14" y={pathStart + index * 14} fill="#aaa5bd" fontSize="10">{line}</text>)}
      <text x="14" y={metadataY - 20} fill="#d4cfff" fontSize="10">{item.fileCount || 0} Python {(item.fileCount || 0) === 1 ? 'file' : 'files'}</text>
      <text x="14" y={metadataY} fill="#aaa5bd" fontSize="10">{metadata}</text>
    </> : <>
      <text x="14" y="28" fill={selected ? '#f7f3ff' : '#eeecf7'} fontSize="13" fontWeight={selected ? '700' : '600'}>{title}</text>
      {pathLines.map((line, index) => <text key={index} x="14" y={pathStart + index * 14} fill="#9894aa" fontSize="10">{line}</text>)}
      <text x="14" y={metadataY} fill={selected ? '#d4cfff' : '#a7a1bc'} fontSize="10">{metadata.length > 44 ? `${metadata.slice(0, 41)}…` : metadata}</text>
    </>}
  </g>
}

function splitPath(path: string): string[] {
  if (path.length <= 46) return [path]
  if (path.length <= 92) {
    const splitAt = path.lastIndexOf('/', 46)
    if (splitAt > 12) return [path.slice(0, splitAt), path.slice(splitAt + 1)]
    return [path.slice(0, 45), path.slice(45)]
  }
  return [`${path.slice(0, 42)}…`, `…${path.slice(-42)}`]
}

export default StructuredDependencyGraph
