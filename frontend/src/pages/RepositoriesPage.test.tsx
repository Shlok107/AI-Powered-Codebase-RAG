import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { makeRepository } from '../test/fixtures'
import { RepositoriesPage } from './RepositoriesPage'

vi.mock('../api/client', () => ({
  api: {
    listRepositories: vi.fn(),
    uploadRepository: vi.fn(),
    deleteRepository: vi.fn(),
  },
}))

function renderRepositories() {
  return render(
    <MemoryRouter initialEntries={['/repositories']}>
      <Routes>
        <Route path="/repositories" element={<RepositoriesPage />} />
        <Route path="/repositories/:repositoryId" element={<h1>Repository details view</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('repository management', () => {
  beforeEach(() => {
    vi.mocked(api.listRepositories).mockResolvedValue({ repositories: [], total: 0 })
  })

  it('shows a loading state while repository data is pending', async () => {
    let resolveRequest!: (value: { repositories: ReturnType<typeof makeRepository>[]; total: number }) => void
    vi.mocked(api.listRepositories).mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve
      }),
    )
    renderRepositories()

    expect(screen.getByRole('status')).toBeInTheDocument()
    resolveRequest({ repositories: [makeRepository()], total: 1 })
    expect(await screen.findByText('payments-service')).toBeInTheDocument()
  })

  it('renders repository metadata and filters by search, status and language', async () => {
    const user = userEvent.setup()
    vi.mocked(api.listRepositories).mockResolvedValue({
      repositories: [
        makeRepository(),
        makeRepository({ id: 'repo-2', display_name: 'web-console', status: 'processing', detected_languages: ['typescript'] }),
        makeRepository({ id: 'repo-3', display_name: 'worker', status: 'failed', detected_languages: ['go'] }),
      ],
      total: 3,
    })
    renderRepositories()

    expect(await screen.findByText('payments-service')).toBeInTheDocument()
    const repoRow = screen.getByRole('link', { name: /payments-service/ }).closest('tr')
    expect(repoRow).toHaveTextContent('12')
    expect(repoRow).toHaveTextContent('26')

    await user.type(screen.getByRole('textbox', { name: 'Search repositories' }), 'web')
    expect(screen.getByText('web-console')).toBeInTheDocument()
    expect(screen.queryByText('payments-service')).not.toBeInTheDocument()

    await user.clear(screen.getByRole('textbox', { name: 'Search repositories' }))
    await user.selectOptions(screen.getByLabelText('Filter by status'), 'failed')
    expect(screen.getByText('worker')).toBeInTheDocument()
    expect(screen.queryByText('web-console')).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Filter by status'), 'all')
    await user.selectOptions(screen.getByLabelText('Filter by language'), 'typescript')
    expect(screen.getByText('web-console')).toBeInTheDocument()
    expect(screen.queryByText('worker')).not.toBeInTheDocument()
  })

  it('shows useful empty and API error states', async () => {
    const user = userEvent.setup()
    renderRepositories()
    expect(await screen.findByText('No repositories yet')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Add repository' })).toHaveLength(2)

    vi.mocked(api.listRepositories).mockRejectedValueOnce({ message: 'API connection failed' })
    await user.click(screen.getByRole('button', { name: /Refresh/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('API connection failed')
  })

  it('rejects a non-ZIP file in the upload form before making an API request', async () => {
    const user = userEvent.setup({ applyAccept: false })
    renderRepositories()
    await screen.findByText('No repositories yet')
    await user.click(screen.getAllByRole('button', { name: 'Add repository' })[0])
    const input = document.querySelector<HTMLInputElement>('#zip-upload')
    expect(input).not.toBeNull()
    await user.upload(input!, new File(['not a zip'], 'notes.txt', { type: 'text/plain' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Choose a ZIP archive to upload.')
    expect(api.uploadRepository).not.toHaveBeenCalled()
  })

  it('uploads the selected ZIP through the API and navigates to the returned repository', async () => {
    const user = userEvent.setup()
    const newRepository = makeRepository({ id: 'repo-uploaded', display_name: 'new-project', status: 'pending' })
    vi.mocked(api.uploadRepository).mockImplementation(async (_file, onProgress) => {
      onProgress?.(62)
      return newRepository
    })
    renderRepositories()
    await screen.findByText('No repositories yet')
    await user.click(screen.getAllByRole('button', { name: 'Add repository' })[0])
    const file = new File(['print("hello")'], 'new-project.zip', { type: 'application/zip' })
    await user.upload(document.querySelector<HTMLInputElement>('#zip-upload')!, file)
    expect(screen.getByText('new-project.zip')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Upload' }))

    await waitFor(() => expect(api.uploadRepository).toHaveBeenCalledWith(file, expect.any(Function)))
    expect(await screen.findByRole('heading', { name: 'Repository details view' })).toBeInTheDocument()
  })

  it('keeps a readable upload error when the server rejects the ZIP', async () => {
    const user = userEvent.setup()
    vi.mocked(api.uploadRepository).mockRejectedValue({ message: 'Archive contains too many files' })
    renderRepositories()
    await screen.findByText('No repositories yet')
    await user.click(screen.getAllByRole('button', { name: 'Add repository' })[0])
    await user.upload(
      document.querySelector<HTMLInputElement>('#zip-upload')!,
      new File(['content'], 'project.zip', { type: 'application/zip' }),
    )
    await user.click(screen.getByRole('button', { name: 'Upload' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Archive contains too many files')
  })

  it('opens a repository using its existing route', async () => {
    const user = userEvent.setup()
    vi.mocked(api.listRepositories).mockResolvedValue({ repositories: [makeRepository()], total: 1 })
    renderRepositories()
    await user.click(await screen.findByRole('link', { name: /payments-service/ }))

    expect(await screen.findByRole('heading', { name: 'Repository details view' })).toBeInTheDocument()
  })
})
