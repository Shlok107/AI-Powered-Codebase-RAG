import type { AxiosAdapter, AxiosInstance, AxiosResponse } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'

describe('API client ZIP upload', () => {
  const client = (api as unknown as { client: AxiosInstance }).client
  const originalAdapter = client.defaults.adapter

  afterEach(() => {
    client.defaults.adapter = originalAdapter
  })

  it('sends the selected File in FormData under file without forcing JSON content type', async () => {
    const file = new File(['print("hello")'], 'project.zip', { type: 'application/zip' })
    let captured: AxiosResponse['config'] | undefined
    const adapter: AxiosAdapter = async (config) => {
      captured = config
      return {
        data: { id: 'repo-1', display_name: 'project', status: 'pending' },
        status: 201,
        statusText: 'Created',
        headers: {},
        config,
      }
    }
    client.defaults.adapter = adapter

    await api.uploadRepository(file, vi.fn())

    expect(captured?.data).toBeInstanceOf(FormData)
    expect((captured?.data as FormData).get('file')).toBe(file)
    expect(captured?.headers.get('Content-Type')).not.toBe('application/json')
    expect(captured?.headers.get('Content-Type')).not.toMatch(/^multipart\/form-data\s*$/i)
  })
})

describe('API client dependency graph', () => {
  const client = (api as unknown as { client: AxiosInstance }).client
  const originalAdapter = client.defaults.adapter

  afterEach(() => {
    client.defaults.adapter = originalAdapter
  })

  it('uses the repository graph, node detail, and impact endpoints with query parameters', async () => {
    const requests: Array<{ url?: string; params?: Record<string, unknown> }> = []
    client.defaults.adapter = async (config) => {
      requests.push({ url: config.url, params: config.params as Record<string, unknown> })
      return { data: {}, status: 200, statusText: 'OK', headers: {}, config }
    }

    await api.getDependencyGraph('repo-1', { query: 'service', relationship_type: 'imports', language: 'python' })
    await api.getDependencyNode('repo-1', 'file:src/api.py')
    await api.getDependencyImpact('repo-1', 'file:src/api.py', 8)

    expect(requests).toEqual([
      { url: '/repositories/repo-1/graph', params: { query: 'service', relationship_type: 'imports', language: 'python' } },
      { url: '/repositories/repo-1/graph/node', params: { node_id: 'file:src/api.py', depth: 1 } },
      { url: '/repositories/repo-1/graph/impact', params: { node_id: 'file:src/api.py', depth: 8 } },
    ])
  })
})
