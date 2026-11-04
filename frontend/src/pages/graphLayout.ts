import type { DependencyGraphNode } from '../types'

export type GraphItemKind = 'file' | 'directory'
export type GraphDirection = 'root' | 'dependency' | 'dependent' | 'transitive-dependency' | 'transitive-dependent'

export interface GraphLayoutItem {
  id: string
  kind: GraphItemKind
  label: string
  path: string
  fileCount?: number
  importCount?: number
  file?: DependencyGraphNode
  direction?: GraphDirection
  relationshipLabel?: string
  x?: number
  y?: number
  height?: number
}

export interface GraphLayoutEdge { source: string; target: string; count: number }
export interface GraphLayout { items: GraphLayoutItem[]; edges: GraphLayoutEdge[]; width: number; height: number }

export const CARD_WIDTH = 300
export const CARD_GAP_X = 104
export const CARD_GAP_Y = 34
const OUTER_GUTTER = 48

export function cardHeight(item: Pick<GraphLayoutItem, 'kind' | 'path'>): number {
  const pathLines = item.path.length > 46 ? 2 : 1
  return item.kind === 'directory' ? 120 + pathLines * 14 : 98 + pathLines * 14
}

function stackHeight(items: GraphLayoutItem[]): number {
  if (!items.length) return 0
  return items.reduce((height, item) => height + cardHeight(item), 0) + CARD_GAP_Y * (items.length - 1)
}

function placeColumn(items: GraphLayoutItem[], x: number, totalHeight: number, topOffset = OUTER_GUTTER): GraphLayoutItem[] {
  let y = topOffset + (totalHeight - stackHeight(items)) / 2
  return items.map(item => {
    const height = cardHeight(item)
    const placed = { ...item, x, y, height }
    y += height + CARD_GAP_Y
    return placed
  })
}

/** Stable layered layout: every rank is a separate column and every card uses its measured layout height. */
export function layoutLayeredGraph(items: GraphLayoutItem[], edges: GraphLayoutEdge[]): GraphLayout {
  if (!items.length) return { items: [], edges, width: 1200, height: 740 }
  const byId = new Map(items.map(item => [item.id, item]))
  const indegree = new Map(items.map(item => [item.id, 0]))
  const outgoing = new Map(items.map(item => [item.id, [] as string[]]))
  for (const edge of edges) {
    if (!byId.has(edge.source) || !byId.has(edge.target)) continue
    outgoing.get(edge.source)!.push(edge.target)
    indegree.set(edge.target, (indegree.get(edge.target) || 0) + 1)
  }

  const rank = new Map<string, number>()
  const ready = items.filter(item => indegree.get(item.id) === 0).map(item => item.id).sort()
  let visited = 0
  while (ready.length) {
    const id = ready.shift()!
    visited += 1
    for (const target of (outgoing.get(id) || []).slice().sort()) {
      rank.set(target, Math.max(rank.get(target) || 0, (rank.get(id) || 0) + 1))
      indegree.set(target, indegree.get(target)! - 1)
      if (indegree.get(target) === 0) { ready.push(target); ready.sort() }
    }
  }
  // Cyclic components cannot be topologically ordered. Keep their cards together in a stable final layer.
  const maxRank = Math.max(0, ...rank.values())
  items.filter(item => !rank.has(item.id) && (visited < items.length)).sort((a, b) => a.id.localeCompare(b.id)).forEach(item => rank.set(item.id, maxRank + 1))
  items.forEach(item => { if (!rank.has(item.id)) rank.set(item.id, 0) })

  const layers = new Map<number, GraphLayoutItem[]>()
  for (const item of items) {
    const value = rank.get(item.id) || 0
    layers.set(value, [...(layers.get(value) || []), item])
  }
  for (const [layer, list] of layers) layers.set(layer, list.slice().sort((a, b) => a.id.localeCompare(b.id)))
  const maxStack = Math.max(...[...layers.values()].map(stackHeight))
  const maxRankValue = Math.max(...layers.keys())
  const positioned = [...layers.entries()].flatMap(([layer, list]) => placeColumn(list, OUTER_GUTTER + layer * (CARD_WIDTH + CARD_GAP_X), maxStack))
  return {
    items: positioned,
    edges: edges.filter(edge => byId.has(edge.source) && byId.has(edge.target)),
    width: OUTER_GUTTER * 2 + (maxRankValue + 1) * CARD_WIDTH + maxRankValue * CARD_GAP_X,
    height: OUTER_GUTTER * 2 + maxStack,
  }
}

/** Places dependencies and dependents in separate columns around the selected file. */
export function layoutFocusGraph(items: GraphLayoutItem[], edges: GraphLayoutEdge[]): GraphLayout {
  const root = items.find(item => item.direction === 'root')
  if (!root) return { items: [], edges: [], width: 1200, height: 740 }
  const columns = [
    items.filter(item => item.direction === 'transitive-dependent').sort((a, b) => a.path.localeCompare(b.path)),
    items.filter(item => item.direction === 'dependent').sort((a, b) => a.path.localeCompare(b.path)),
    [root],
    items.filter(item => item.direction === 'dependency').sort((a, b) => a.path.localeCompare(b.path)),
    items.filter(item => item.direction === 'transitive-dependency').sort((a, b) => a.path.localeCompare(b.path)),
  ]
  const maxStack = Math.max(...columns.map(stackHeight))
  const hasOuter = columns[0].length > 0 || columns[4].length > 0
  const activeColumns = hasOuter ? columns : columns.slice(1, 4)
  const rootColumn = activeColumns.indexOf(columns[2])
  const graphWidth = OUTER_GUTTER * 2 + activeColumns.length * CARD_WIDTH + (activeColumns.length - 1) * CARD_GAP_X
  const rootX = OUTER_GUTTER + rootColumn * (CARD_WIDTH + CARD_GAP_X)
  const headingHeight = 56
  const positioned = activeColumns.flatMap((column, index) => placeColumn(column, OUTER_GUTTER + index * (CARD_WIDTH + CARD_GAP_X), maxStack, headingHeight))
  const width = Math.max(graphWidth, rootX + CARD_WIDTH + OUTER_GUTTER)
  return {
    items: positioned,
    edges: edges.filter(edge => positioned.some(item => item.id === edge.source) && positioned.some(item => item.id === edge.target)),
    width,
    height: headingHeight + maxStack + OUTER_GUTTER,
  }
}

export function findOverlappingCards(items: GraphLayoutItem[], minimumGap = 0): Array<[string, string]> {
  const overlaps: Array<[string, string]> = []
  for (let i = 0; i < items.length; i += 1) {
    const a = items[i]
    for (let j = i + 1; j < items.length; j += 1) {
      const b = items[j]
      const separated = (a.x! + CARD_WIDTH + minimumGap <= b.x!) || (b.x! + CARD_WIDTH + minimumGap <= a.x!) || (a.y! + a.height! + minimumGap <= b.y!) || (b.y! + b.height! + minimumGap <= a.y!)
      if (!separated) overlaps.push([a.id, b.id])
    }
  }
  return overlaps
}

export function fitGraphTransform(viewportWidth: number, viewportHeight: number, graphWidth: number, graphHeight: number, reservedWidth = 0): { x: number; y: number; scale: number } {
  const availableWidth = Math.max(320, viewportWidth - reservedWidth)
  const pad = 42
  const scale = Math.max(.06, Math.min(1.25, (availableWidth - pad * 2) / graphWidth, (viewportHeight - pad * 2) / graphHeight))
  return { scale, x: (availableWidth - graphWidth * scale) / 2, y: (viewportHeight - graphHeight * scale) / 2 }
}
