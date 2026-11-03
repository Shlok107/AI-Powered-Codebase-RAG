import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { api } from './api/client'

vi.mock('./api/client', () => ({
  api: {
    health: vi.fn(),
    listRepositories: vi.fn(),
  },
}))

vi.mock('./components/NetworkBackground', () => ({ NetworkBackground: () => null }))

describe('application navigation', () => {
  beforeEach(() => {
    vi.mocked(api.health).mockResolvedValue({
      status: 'healthy',
      database: 'connected',
      llm_provider: 'configured',
      embedding_provider: 'configured',
    })
    vi.mocked(api.listRepositories).mockResolvedValue({ repositories: [], total: 0 })
  })

  it('routes from overview to repositories and marks the current navigation item active', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument()
    const repositoriesLink = screen.getByRole('link', { name: 'Repositories' })
    fireEvent.click(repositoriesLink)

    expect(await screen.findByRole('heading', { name: 'Repositories' })).toBeInTheDocument()
    await waitFor(() => expect(repositoriesLink).toHaveAttribute('aria-current', 'page'))
  })

  it('keeps the existing Ask Codebase route and renders its indexed repository selector', async () => {
    vi.mocked(api.listRepositories).mockResolvedValue({
      repositories: [
        {
          id: 'repo-1',
          display_name: 'payments-service',
          source_type: 'zip_upload',
          source_metadata: {},
          status: 'indexed',
          detected_languages: ['python'],
          file_count: 4,
          chunk_count: 8,
          error_summary: null,
          indexed_at: null,
          created_at: '2026-11-01T10:00:00.000Z',
          updated_at: '2026-11-02T10:00:00.000Z',
        },
      ],
      total: 1,
    })
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'Ask Codebase' })).toBeInTheDocument()
    expect(screen.getByText('payments-service')).toBeInTheDocument()
  })
})
