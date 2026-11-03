import { useEffect, useRef } from 'react'

interface NetworkNode {
  baseX: number
  baseY: number
  x: number
  y: number
  targetX: number
  targetY: number
  radius: number
  opacity: number
  directActivation: number
  targetActivation: number
  activation: number
}

interface NetworkEdge {
  from: number
  to: number
}

interface NodePair {
  a: number
  b: number
}

interface NetworkGeometry {
  edges: NetworkEdge[]
  collisionPairs: NodePair[]
}

const INTERACTION_RADIUS = 208
const MAX_NODE_DISPLACEMENT = 24
const MAX_CONNECTIONS_PER_NODE = 4

function createRandom(width: number, height: number): () => number {
  let state = (
    Math.imul(Math.round(width), 73856093) ^
    Math.imul(Math.round(height), 19349663) ^
    0x51a7c3d9
  ) >>> 0

  if (state === 0) state = 0x6d2b79f5

  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let value = state
    value = Math.imul(value ^ (value >>> 15), value | 1)
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61)
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296
  }
}

function createPoissonNodes(width: number, height: number, minimumDistance: number): NetworkNode[] {
  const random = createRandom(width, height)
  const cellSize = minimumDistance / Math.SQRT2
  const columns = Math.max(1, Math.ceil(width / cellSize))
  const rows = Math.max(1, Math.ceil(height / cellSize))
  const grid = new Int32Array(columns * rows)
  grid.fill(-1)

  const nodes: NetworkNode[] = []
  const active: number[] = []
  const maxNodes = Math.min(
    220,
    Math.max(24, Math.ceil((width * height) / (minimumDistance * minimumDistance) * 1.25)),
  )

  const addNode = (x: number, y: number) => {
    const index = nodes.length
    nodes.push({
      baseX: x,
      baseY: y,
      x,
      y,
      targetX: x,
      targetY: y,
      radius: 1.1 + random() * 0.5,
      opacity: 0.28 + random() * 0.2,
      directActivation: 0,
      targetActivation: 0,
      activation: 0,
    })
    grid[Math.floor(y / cellSize) * columns + Math.floor(x / cellSize)] = index
    active.push(index)
  }

  addNode(random() * width, random() * height)

  while (active.length > 0 && nodes.length < maxNodes) {
    const activeSlot = Math.floor(random() * active.length)
    const source = nodes[active[activeSlot]]
    let placed = false

    for (let attempt = 0; attempt < 30; attempt += 1) {
      const angle = random() * Math.PI * 2
      const distance = minimumDistance * (1 + random())
      const x = source.baseX + Math.cos(angle) * distance
      const y = source.baseY + Math.sin(angle) * distance
      if (x < 0 || x >= width || y < 0 || y >= height) continue

      const cellX = Math.floor(x / cellSize)
      const cellY = Math.floor(y / cellSize)
      let clear = true
      for (let offsetY = -3; offsetY <= 3 && clear; offsetY += 1) {
        for (let offsetX = -3; offsetX <= 3; offsetX += 1) {
          const neighborX = cellX + offsetX
          const neighborY = cellY + offsetY
          if (neighborX < 0 || neighborX >= columns || neighborY < 0 || neighborY >= rows) continue

          const neighborIndex = grid[neighborY * columns + neighborX]
          if (neighborIndex < 0) continue
          const dx = nodes[neighborIndex].baseX - x
          const dy = nodes[neighborIndex].baseY - y
          if (dx * dx + dy * dy < minimumDistance * minimumDistance) {
            clear = false
            break
          }
        }
      }

      if (clear) {
        addNode(x, y)
        placed = true
        break
      }
    }

    if (!placed) {
      active[activeSlot] = active[active.length - 1]
      active.pop()
    }
  }

  return nodes
}

function orientation(ax: number, ay: number, bx: number, by: number, cx: number, cy: number): number {
  return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
}

function crossesExistingEdge(
  candidate: NetworkEdge,
  edges: NetworkEdge[],
  nodes: NetworkNode[],
): boolean {
  const a = nodes[candidate.from]
  const b = nodes[candidate.to]

  for (const edge of edges) {
    if (edge.from === candidate.from || edge.from === candidate.to || edge.to === candidate.from || edge.to === candidate.to) continue
    const c = nodes[edge.from]
    const d = nodes[edge.to]
    const abC = orientation(a.baseX, a.baseY, b.baseX, b.baseY, c.baseX, c.baseY)
    const abD = orientation(a.baseX, a.baseY, b.baseX, b.baseY, d.baseX, d.baseY)
    const cdA = orientation(c.baseX, c.baseY, d.baseX, d.baseY, a.baseX, a.baseY)
    const cdB = orientation(c.baseX, c.baseY, d.baseX, d.baseY, b.baseX, b.baseY)
    if (abC * abD < 0 && cdA * cdB < 0) return true
  }

  return false
}

function createNetworkGeometry(nodes: NetworkNode[], minimumDistance: number): NetworkGeometry {
  const maxConnectionDistance = minimumDistance * 1.78
  const maxConnectionDistanceSquared = maxConnectionDistance * maxConnectionDistance
  const minimumSeparation = minimumDistance * 0.56
  const maxCollisionDistance = minimumSeparation + MAX_NODE_DISPLACEMENT * 2
  const maxCollisionDistanceSquared = maxCollisionDistance * maxCollisionDistance
  const candidates: Array<NetworkEdge & { distanceSquared: number }> = []
  const collisionPairs: NodePair[] = []

  for (let from = 0; from < nodes.length; from += 1) {
    for (let to = from + 1; to < nodes.length; to += 1) {
      const dx = nodes[from].baseX - nodes[to].baseX
      const dy = nodes[from].baseY - nodes[to].baseY
      const distanceSquared = dx * dx + dy * dy
      if (distanceSquared <= maxConnectionDistanceSquared) {
        candidates.push({ from, to, distanceSquared })
      }
      if (distanceSquared <= maxCollisionDistanceSquared) {
        collisionPairs.push({ a: from, b: to })
      }
    }
  }

  candidates.sort((a, b) => a.distanceSquared - b.distanceSquared)
  const edges: NetworkEdge[] = []
  const degrees = new Uint8Array(nodes.length)
  const edgeKeys = new Set<string>()

  const addIfAvailable = (candidate: NetworkEdge) => {
    const key = `${candidate.from}:${candidate.to}`
    if (edgeKeys.has(key)) return
    if (degrees[candidate.from] >= MAX_CONNECTIONS_PER_NODE || degrees[candidate.to] >= MAX_CONNECTIONS_PER_NODE) return
    if (crossesExistingEdge(candidate, edges, nodes)) return
    edges.push({ from: candidate.from, to: candidate.to })
    edgeKeys.add(key)
    degrees[candidate.from] += 1
    degrees[candidate.to] += 1
  }

  for (const candidate of candidates) addIfAvailable(candidate)

  for (let nodeIndex = 0; nodeIndex < nodes.length; nodeIndex += 1) {
    if (degrees[nodeIndex] >= 2) continue
    for (const candidate of candidates) {
      if (candidate.from !== nodeIndex && candidate.to !== nodeIndex) continue
      addIfAvailable(candidate)
      if (degrees[nodeIndex] >= 2) break
    }
  }

  return { edges, collisionPairs }
}

function separateTargets(nodes: NetworkNode[], pairs: NodePair[], width: number, height: number, minimumDistance: number) {
  const minimumSeparation = minimumDistance * 0.56

  for (let pass = 0; pass < 2; pass += 1) {
    for (const pair of pairs) {
      const a = nodes[pair.a]
      const b = nodes[pair.b]
      let dx = b.targetX - a.targetX
      let dy = b.targetY - a.targetY
      let distance = Math.sqrt(dx * dx + dy * dy)
      if (distance >= minimumSeparation) continue

      if (distance < 0.001) {
        const angle = (pair.a * 12.9898 + pair.b * 78.233) % (Math.PI * 2)
        dx = Math.cos(angle)
        dy = Math.sin(angle)
        distance = 1
      }

      const correction = (minimumSeparation - distance) * 0.5
      const offsetX = (dx / distance) * correction
      const offsetY = (dy / distance) * correction
      a.targetX -= offsetX
      a.targetY -= offsetY
      b.targetX += offsetX
      b.targetY += offsetY
    }
  }

  for (const node of nodes) {
    node.targetX = Math.max(2, Math.min(width - 2, node.targetX))
    node.targetY = Math.max(2, Math.min(height - 2, node.targetY))
  }
}

export function NetworkBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d', { alpha: true })
    if (!canvas || !context) return

    let width = 0
    let height = 0
    let pixelRatio = 1
    let minimumDistance = 0
    let nodes: NetworkNode[] = []
    let edges: NetworkEdge[] = []
    let collisionPairs: NodePair[] = []
    let canvasLeft = 0
    let canvasTop = 0
    let pointerX = 0
    let pointerY = 0
    let pointerInside = false
    let frameId: number | null = null
    let lastFrameTime = 0
    let canInteract = false

    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const pointerPreference = window.matchMedia('(hover: hover) and (pointer: fine)')

    const draw = () => {
      context.clearRect(0, 0, width, height)
      context.lineWidth = 0.65
      context.strokeStyle = '#d8d9e2'

      for (const edge of edges) {
        const from = nodes[edge.from]
        const to = nodes[edge.to]
        const activation = Math.max(from.activation, to.activation)
        context.globalAlpha = 0.075 + activation * 0.26
        context.lineWidth = 0.62 + activation * 0.16
        context.beginPath()
        context.moveTo(from.x, from.y)
        context.lineTo(to.x, to.y)
        context.stroke()
      }

      context.fillStyle = '#f7f7fb'
      for (const node of nodes) {
        const scale = 1 + Math.min(0.52, node.activation * 0.52)
        const radius = node.radius * scale
        if (node.activation > 0.04) {
          context.globalAlpha = node.activation * 0.075
          context.beginPath()
          context.arc(node.x, node.y, radius * 3.2, 0, Math.PI * 2)
          context.fill()
        }
        context.globalAlpha = Math.min(0.96, node.opacity + node.activation * 0.5)
        context.beginPath()
        context.arc(node.x, node.y, radius, 0, Math.PI * 2)
        context.fill()
      }

      context.globalAlpha = 1
    }

    const render = (time: number) => {
      frameId = null
      const delta = lastFrameTime === 0 ? 1 : Math.max(0.5, Math.min(2, (time - lastFrameTime) / 16.667))
      lastFrameTime = time
      let settling = false

      for (const node of nodes) {
        let influence = 0
        let dx = 0
        let dy = 0

        if (canInteract && pointerInside) {
          dx = pointerX - node.baseX
          dy = pointerY - node.baseY
          const distance = Math.sqrt(dx * dx + dy * dy)
          if (distance < INTERACTION_RADIUS) {
            const falloff = 1 - distance / INTERACTION_RADIUS
            influence = falloff * falloff * (3 - 2 * falloff)
            const pull = Math.min(MAX_NODE_DISPLACEMENT * influence, distance * 0.36)
            if (distance > 0.001) {
              node.targetX = node.baseX + (dx / distance) * pull
              node.targetY = node.baseY + (dy / distance) * pull
            } else {
              node.targetX = node.baseX
              node.targetY = node.baseY
            }
          } else {
            node.targetX = node.baseX
            node.targetY = node.baseY
          }
        } else {
          node.targetX = node.baseX
          node.targetY = node.baseY
        }

        node.directActivation = influence
        node.targetActivation = influence
      }

      if (canInteract && pointerInside) {
        for (const edge of edges) {
          const fromActivation = nodes[edge.from].directActivation
          const toActivation = nodes[edge.to].directActivation
          nodes[edge.to].targetActivation = Math.max(nodes[edge.to].targetActivation, fromActivation * 0.18)
          nodes[edge.from].targetActivation = Math.max(nodes[edge.from].targetActivation, toActivation * 0.18)
        }
        separateTargets(nodes, collisionPairs, width, height, minimumDistance)
      }

      for (const node of nodes) {
        const errorX = node.targetX - node.x
        const errorY = node.targetY - node.y
        const positionEase = 1 - Math.exp(-0.1 * delta)
        node.x += errorX * positionEase
        node.y += errorY * positionEase

        const activationDifference = node.targetActivation - node.activation
        node.activation += activationDifference * (1 - Math.exp(-0.12 * delta))

        if (Math.abs(errorX) > 0.1 || Math.abs(errorY) > 0.1 || Math.abs(activationDifference) > 0.0025) {
          settling = true
        } else {
          node.x = node.targetX
          node.y = node.targetY
          node.activation = node.targetActivation
        }
      }

      draw()
      if (settling) frameId = window.requestAnimationFrame(render)
      else lastFrameTime = 0
    }

    const scheduleFrame = () => {
      if (frameId === null) frameId = window.requestAnimationFrame(render)
    }

    const resize = () => {
      const bounds = canvas.getBoundingClientRect()
      const nextWidth = bounds.width
      const nextHeight = bounds.height
      const nextPixelRatio = Math.min(window.devicePixelRatio || 1, 1.75)
      if (Math.abs(nextWidth - width) < 0.5 && Math.abs(nextHeight - height) < 0.5 && nextPixelRatio === pixelRatio) return

      width = nextWidth
      height = nextHeight
      canvasLeft = bounds.left
      canvasTop = bounds.top
      pixelRatio = nextPixelRatio
      pointerInside = false
      lastFrameTime = 0

      canvas.width = Math.max(1, Math.round(width * pixelRatio))
      canvas.height = Math.max(1, Math.round(height * pixelRatio))
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)

      if (!width || !height) {
        nodes = []
        edges = []
        collisionPairs = []
        return
      }

      minimumDistance = Math.max(64, Math.sqrt((width * height) / 172))
      nodes = createPoissonNodes(width, height, minimumDistance)
      const geometry = createNetworkGeometry(nodes, minimumDistance)
      edges = geometry.edges
      collisionPairs = geometry.collisionPairs
      draw()
    }

    const updateInteractionPreference = () => {
      canInteract = pointerPreference.matches && !motionPreference.matches
      if (!canInteract) {
        pointerInside = false
        if (frameId !== null) {
          window.cancelAnimationFrame(frameId)
          frameId = null
        }
        lastFrameTime = 0
        for (const node of nodes) {
          node.x = node.baseX
          node.y = node.baseY
          node.targetX = node.baseX
          node.targetY = node.baseY
          node.activation = 0
          node.targetActivation = 0
        }
        draw()
      }
    }

    const handlePointerMove = (event: PointerEvent) => {
      if (!canInteract || event.pointerType === 'touch') return
      const x = event.clientX - canvasLeft
      const y = event.clientY - canvasTop
      const inside = x >= 0 && x <= width && y >= 0 && y <= height
      const wasInside = pointerInside
      if (inside) {
        pointerX = x
        pointerY = y
      }
      pointerInside = inside
      if (inside || wasInside) scheduleFrame()
    }

    const handlePointerLeave = () => {
      if (!canInteract) return
      pointerInside = false
      scheduleFrame()
    }

    const handleWindowResize = () => resize()
    const observer = new ResizeObserver(resize)
    observer.observe(canvas)
    window.addEventListener('resize', handleWindowResize, { passive: true })
    window.addEventListener('pointermove', handlePointerMove, { passive: true })
    window.addEventListener('pointerleave', handlePointerLeave)
    window.addEventListener('blur', handlePointerLeave)
    motionPreference.addEventListener('change', updateInteractionPreference)
    pointerPreference.addEventListener('change', updateInteractionPreference)

    updateInteractionPreference()
    resize()

    return () => {
      observer.disconnect()
      window.removeEventListener('resize', handleWindowResize)
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerleave', handlePointerLeave)
      window.removeEventListener('blur', handlePointerLeave)
      motionPreference.removeEventListener('change', updateInteractionPreference)
      pointerPreference.removeEventListener('change', updateInteractionPreference)
      if (frameId !== null) window.cancelAnimationFrame(frameId)
    }
  }, [])

  return <canvas
    ref={canvasRef}
    className="pointer-events-none absolute inset-0 z-0 h-full w-full"
    aria-hidden="true"
  />
}
