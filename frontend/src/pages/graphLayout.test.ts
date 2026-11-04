import { describe, expect, it } from 'vitest'
import { cardHeight, findOverlappingCards, fitGraphTransform, layoutFocusGraph, layoutLayeredGraph, type GraphLayoutItem } from './graphLayout'

function file(path: string, direction: GraphLayoutItem['direction'] = 'dependency'): GraphLayoutItem {
  return { id: `file:${path}`, kind: 'file', label: path.split('/').pop() || path, path, direction, relationshipLabel: direction === 'dependent' ? 'Imports selected file' : 'Imported by selected file' }
}

function focusedGraph(incoming: number, outgoing: number) {
  const root = { ...file('src/selected.py', 'root'), id: 'file:src/selected.py' }
  const items = [root,
    ...Array.from({ length: incoming }, (_, i) => file(`tests/consumer_${i}.py`, 'dependent')),
    ...Array.from({ length: outgoing }, (_, i) => file(`src/service_${i}.py`, 'dependency')),
  ]
  const edges = [
    ...items.filter(item => item.direction === 'dependent').map(item => ({ source: item.id, target: root.id, count: 1 })),
    ...items.filter(item => item.direction === 'dependency').map(item => ({ source: root.id, target: item.id, count: 1 })),
  ]
  return layoutFocusGraph(items, edges)
}

describe('dependency graph layout', () => {
  it.each([[1, 1], [4, 1], [1, 10], [10, 10], [30, 4]])('keeps %i incoming and %i outgoing cards separated', (incoming, outgoing) => {
    const graph = focusedGraph(incoming, outgoing)
    expect(findOverlappingCards(graph.items)).toEqual([])
    expect(graph.height).toBeGreaterThan(cardHeight(graph.items.find(item => item.direction === 'root')!))
    expect(graph.items).toHaveLength(incoming + outgoing + 1)
    const root = graph.items.find(item => item.direction === 'root')!
    expect(root.x).toBeGreaterThan(0)
    expect(graph.edges).toHaveLength(incoming + outgoing)
  })

  it('allocates extra vertical room for long paths that render on two lines', () => {
    const short = file('src/a.py')
    const long = file(`packages/${'nested/'.repeat(9)}source_module.py`)
    expect(cardHeight(long)).toBeGreaterThan(cardHeight(short))
    const graph = layoutFocusGraph([
      { ...file('src/root.py', 'root'), id: 'root' },
      { ...short, id: 'short', direction: 'dependent' },
      { ...long, id: 'long', direction: 'dependent' },
    ], [])
    expect(findOverlappingCards(graph.items)).toEqual([])
    const longItem = graph.items.find(item => item.id === 'long')!
    expect(longItem.height).toBe(cardHeight(long))
  })

  it('adds vertical workspace as relationship lists grow instead of compressing cards', () => {
    expect(focusedGraph(30, 4).height).toBeGreaterThan(focusedGraph(4, 4).height)
  })

  it('keeps layered overview cards apart across branches, cycles and isolated nodes', () => {
    const items = Array.from({ length: 14 }, (_, index) => file(`app/module_${index}.py`))
    const edges = [
      { source: items[0].id, target: items[2].id, count: 1 },
      { source: items[0].id, target: items[3].id, count: 1 },
      { source: items[2].id, target: items[0].id, count: 1 },
      { source: items[4].id, target: items[5].id, count: 1 },
    ]
    const graph = layoutLayeredGraph(items, edges)
    expect(findOverlappingCards(graph.items)).toEqual([])
    expect(graph.items).toHaveLength(items.length)
    expect(graph.width).toBeGreaterThan(1200)
  })

  it.each([[1440, 900], [1206, 672], [1024, 768], [820, 700]])('fits and reserves the details panel at %i × %i', (width, height) => {
    const graph = focusedGraph(10, 8)
    const fit = fitGraphTransform(width, height, graph.width, graph.height, width >= 1024 ? 324 : 0)
    const availableWidth = Math.max(320, width - (width >= 1024 ? 324 : 0))
    expect(fit.scale).toBeGreaterThan(0)
    expect(fit.x).toBeGreaterThanOrEqual(0)
    expect(fit.x + graph.width * fit.scale).toBeLessThanOrEqual(availableWidth + 0.01)
    expect(fit.y + graph.height * fit.scale).toBeLessThanOrEqual(height + 0.01)
  })
})
