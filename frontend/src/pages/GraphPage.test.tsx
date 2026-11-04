import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { DependencyGraphResponse, DependencyNodeDetails } from '../types'
import { makeRepository } from '../test/fixtures'
import { GraphPage } from './GraphPage'

vi.mock('../api/client', () => ({
  api: {
    listRepositories: vi.fn(),
    getDependencyGraph: vi.fn(),
    getDependencyNode: vi.fn(),
    getDependencyImpact: vi.fn(),
  },
}))

const graph: DependencyGraphResponse = {
  repository_id: 'repo-1', repository_name: 'payments-service',
  nodes: [
    { id: 'file:src/api.py', type: 'file', label: 'api.py', path: 'src/api.py', language: 'python', degree: 1, x: -1, y: 0 },
    { id: 'file:src/service.py', type: 'file', label: 'service.py', path: 'src/service.py', language: 'python', degree: 1, x: 1, y: 0 },
    { id: 'file:tests/test_api.py', type: 'file', label: 'test_api.py', path: 'tests/test_api.py', language: 'python', degree: 1, x: 0, y: 1 },
    { id: 'file:tests/test_service.py', type: 'file', label: 'test_service.py', path: 'tests/test_service.py', language: 'python', degree: 1, x: 0, y: 2 },
  ],
  edges: [
    { source: 'file:src/api.py', target: 'file:src/service.py', type: 'imports', source_lines: [2] },
    { source: 'file:tests/test_api.py', target: 'file:src/api.py', type: 'imports', source_lines: [2] },
    { source: 'file:tests/test_service.py', target: 'file:src/service.py', type: 'imports', source_lines: [2] },
  ],
  files_analyzed: 6, python_files: 4, resolved_relationships: 3, parse_errors: 0, truncated: false,
  coverage: { languages: ['python'], relationship_types: ['imports'], partial: true },
}
const details: DependencyNodeDetails = {
  repository_id: 'repo-1', depth: 1, node: graph.nodes[0],
  direct_dependencies: ['src/service.py'], direct_dependents: ['tests/test_api.py'], dependencies: ['src/service.py'], dependents: ['tests/test_api.py'],
  dependency_count: 1, dependent_count: 1,
}

describe('dependency graph workspace', () => {
  beforeEach(() => {
    vi.mocked(api.listRepositories).mockResolvedValue({ repositories: [makeRepository()], total: 1 })
    vi.mocked(api.getDependencyGraph).mockResolvedValue(graph)
    vi.mocked(api.getDependencyNode).mockResolvedValue(details)
    vi.mocked(api.getDependencyImpact).mockResolvedValue({ repository_id: 'repo-1', node_id: 'file:src/api.py', depth: 8, affected_dependents: ['src/consumer.py'], direct_dependents: [] })
  })

  it('loads actual indexed repository graph data and reports supported coverage', async () => {
    render(<GraphPage />)
    expect(await screen.findByRole('img', { name: 'Repository directory dependency overview' })).toBeInTheDocument()
    expect(screen.getByText('Python imports')).toBeInTheDocument()
    expect(screen.getByText('Partial language coverage')).toBeInTheDocument()
    expect(screen.getByText('Python files analyzed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /src; 2 Python files/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /tests; 2 Python files/ })).toBeInTheDocument()
    expect(api.getDependencyGraph).toHaveBeenCalledWith('repo-1')
  })

  it('opens a directory, drills into files, and focuses a file with incoming and outgoing relationships', async () => {
    const user = userEvent.setup()
    render(<GraphPage />)
    await screen.findByRole('img', { name: 'Repository directory dependency overview' })
    await user.click(screen.getByRole('button', { name: /src; 2 Python files/ }))
    expect(await screen.findByRole('img', { name: 'Files and imports in src' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /^src\/api\.py;/ }))
    expect(await screen.findByRole('img', { name: 'Focused dependency graph for src/api.py' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /src\/api\.py; 1 direct imports · 1 importers/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /tests\/test_api\.py; Imports selected file/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /src\/service\.py; Imported by selected file/ })).toBeInTheDocument()
    expect(await screen.findByRole('complementary', { name: 'Selected file details' })).toHaveTextContent('service.py')
    expect(screen.getByRole('complementary', { name: 'Selected file details' })).toHaveTextContent('test_api.py')
    expect(api.getDependencyNode).toHaveBeenCalledWith('repo-1', 'file:src/api.py', 1)
  })

  it('searches the API result and opens a focused file view with impact and depth controls', async () => {
    const user = userEvent.setup()
    render(<GraphPage />)
    await screen.findByRole('img', { name: 'Repository directory dependency overview' })
    const searchInput = screen.getByRole('textbox', { name: 'Search graph files' })
    await user.type(searchInput, 'api.py')
    await user.click(await screen.findByRole('button', { name: 'src/api.py' }))

    expect(await screen.findByRole('img', { name: 'Focused dependency graph for src/api.py' })).toBeInTheDocument()
    expect(await screen.findByRole('complementary', { name: 'Selected file details' })).toBeInTheDocument()
    expect(screen.getByRole('complementary', { name: 'Selected file details' })).toHaveTextContent('service.py')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Dependency depth' }), '2')
    await waitFor(() => expect(api.getDependencyNode).toHaveBeenCalledWith('repo-1', 'file:src/api.py', 2))
    await user.click(screen.getByRole('button', { name: 'Show impact view' }))
    await waitFor(() => expect(api.getDependencyImpact).toHaveBeenCalledWith('repo-1', 'file:src/api.py', 2))

    await user.clear(searchInput)
    await user.type(searchInput, 'service')
    await waitFor(() => expect(api.getDependencyGraph).toHaveBeenLastCalledWith('repo-1', { query: 'service' }))
    const matchingFiles = await screen.findAllByRole('button', { name: 'src/service.py' })
    expect(matchingFiles.length).toBeGreaterThanOrEqual(1)
    await user.click(matchingFiles[0])
    expect(await screen.findByRole('img', { name: 'Focused dependency graph for src/service.py' })).toBeInTheDocument()
  })

  it('supports wheel zoom and reset without refetching the graph', async () => {
    render(<GraphPage />)
    const graphView = await screen.findByRole('img', { name: 'Repository directory dependency overview' })
    const transformed = graphView.querySelector('g[transform^="translate("]')
    const before = transformed?.getAttribute('transform')
    fireEvent.wheel(graphView, { deltaY: -160, clientX: 200, clientY: 140 })
    await waitFor(() => expect(transformed?.getAttribute('transform')).not.toBe(before))
    const callsBeforeReset = vi.mocked(api.getDependencyGraph).mock.calls.length
    await userEvent.setup().click(screen.getByRole('button', { name: 'Reset graph layout' }))
    expect(api.getDependencyGraph).toHaveBeenCalledTimes(callsBeforeReset)
  })

  it('distinguishes repositories without internal imports from an unindexed repository', async () => {
    vi.mocked(api.getDependencyGraph).mockResolvedValue({ ...graph, nodes: graph.nodes, edges: [], python_files: 4, resolved_relationships: 0 })
    render(<GraphPage />)
    expect(await screen.findByText('No internal imports detected')).toBeInTheDocument()

    vi.mocked(api.listRepositories).mockResolvedValue({ repositories: [], total: 0 })
    render(<GraphPage />)
    expect(await screen.findByText('No indexed repositories')).toBeInTheDocument()
  })

  it('shows a retryable graph loading error', async () => {
    vi.mocked(api.getDependencyGraph).mockRejectedValueOnce({ message: 'Graph request failed' }).mockResolvedValueOnce(graph)
    const user = userEvent.setup()
    render(<GraphPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Graph request failed')
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('img', { name: 'Repository directory dependency overview' })).toBeInTheDocument()
  })
})
