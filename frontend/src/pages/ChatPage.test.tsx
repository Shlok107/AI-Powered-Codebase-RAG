import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { makeRepository } from '../test/fixtures'
import { ChatPage } from './ChatPage'

vi.mock('../api/client', () => ({
  api: {
    getRepository: vi.fn(),
    chat: vi.fn(),
  },
}))

function renderChat() {
  return render(
    <MemoryRouter initialEntries={['/chat/repo-1']}>
      <Routes>
        <Route path="/chat/:repositoryId" element={<ChatPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const citation = {
  chunk_id: 'eb2d11fd-0d5f-42db-92b6-077c17a02399',
  file_path: 'src/handler.py',
  start_line: 18,
  end_line: 21,
  language: 'python',
  relevance_score: 0.83,
  excerpt: 'def handle_request():\n    return 42',
}

describe('Ask Codebase', () => {
  beforeEach(() => {
    vi.mocked(api.getRepository).mockResolvedValue(makeRepository())
  })

  it('validates empty questions, submits a real question and renders source citations', async () => {
    const user = userEvent.setup()
    vi.mocked(api.chat).mockResolvedValue({
      answer: 'The handler returns 42 [Source 1].',
      citations: [citation],
      conversation_id: 'conversation-1',
      model_used: 'nvidia/nemotron-test',
      retrieval_time_ms: 12,
      generation_time_ms: 34,
    })
    renderChat()

    const sendButton = await screen.findByRole('button', { name: 'Send question' })
    expect(sendButton).toBeDisabled()
    const questionInput = screen.getByPlaceholderText(/Ask about an implementation/)
    await user.type(questionInput, 'Where does request handling happen?')
    expect(sendButton).toBeEnabled()
    await user.click(sendButton)

    expect(await screen.findByText('The handler returns 42 [Source 1].')).toBeInTheDocument()
    expect(api.chat).toHaveBeenCalledWith('repo-1', 'Where does request handling happen?')
    const citationButton = screen.getByRole('button', {
      name: 'Open source src/handler.py, lines 18 to 21',
    })
    await user.click(citationButton)

    const sourcePanel = screen.getByRole('complementary', { name: 'Source inspection' })
    expect(within(sourcePanel).getByText('src/handler.py')).toBeInTheDocument()
    expect(within(sourcePanel).getByText('L18–L21')).toBeInTheDocument()
    expect(within(sourcePanel).getByText(/def handle_request/)).toBeInTheDocument()
  })

  it('shows the server failure in the conversation and restores the input controls', async () => {
    const user = userEvent.setup()
    vi.mocked(api.chat).mockRejectedValue({ message: 'Retrieval is unavailable' })
    renderChat()
    const questionInput = await screen.findByPlaceholderText(/Ask about an implementation/)
    await user.type(questionInput, 'Explain this module')
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(await screen.findByText('Retrieval is unavailable')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled())
  })

  it('shows a status notice and disables chat while a repository is not indexed', async () => {
    vi.mocked(api.getRepository).mockResolvedValue(makeRepository({ status: 'processing' }))
    renderChat()

    expect(await screen.findByText(/available after indexing completes/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled()
    expect(screen.getByPlaceholderText(/available when indexing completes/)).toBeDisabled()
  })

  it('returns to the repository list when the selected repository cannot be loaded', async () => {
    vi.mocked(api.getRepository).mockRejectedValue({ message: 'Repository service unavailable' })
    renderChat()

    expect(await screen.findByRole('heading', { name: 'Could not open repository' })).toBeInTheDocument()
    expect(screen.getByText('Repository service unavailable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Back to Repositories' })).toBeInTheDocument()
  })
})
