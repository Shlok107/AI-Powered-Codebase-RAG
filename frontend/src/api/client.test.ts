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
