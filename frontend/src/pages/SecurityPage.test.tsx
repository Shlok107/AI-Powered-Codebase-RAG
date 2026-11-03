import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { makeFinding, makeRepository, makeScan } from '../test/fixtures'
import { SecurityPage } from './SecurityPage'

vi.mock('../api/client', () => ({
  api: {
    getRepository: vi.fn(),
    listScans: vi.fn(),
    listFindings: vi.fn(),
    runScan: vi.fn(),
    updateFinding: vi.fn(),
  },
}))

function renderSecurity() {
  return render(
    <MemoryRouter initialEntries={['/security/repo-1']}>
      <Routes>
        <Route path="/security/:repositoryId" element={<SecurityPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('security findings workspace', () => {
  beforeEach(() => {
    vi.mocked(api.getRepository).mockResolvedValue(makeRepository())
    vi.mocked(api.listScans).mockResolvedValue([makeScan()])
    vi.mocked(api.listFindings).mockResolvedValue({ findings: [makeFinding()], total: 1 })
    vi.mocked(api.runScan).mockResolvedValue(makeScan({ id: 'scan-2', status: 'queued' }))
    vi.mocked(api.updateFinding).mockImplementation(async (_id, status) => makeFinding({ status }))
  })

  it('renders real finding severity, path and line metadata and opens the remediation detail', async () => {
    const user = userEvent.setup()
    renderSecurity()

    expect(await screen.findByRole('heading', { name: 'Security findings' })).toBeInTheDocument()
    const inspectButton = screen.getByRole('button', { name: 'Inspect Dynamic evaluation detected' })
    const findingRow = inspectButton.closest('tr')
    expect(findingRow).not.toBeNull()
    expect(within(findingRow!).getByText('high')).toBeInTheDocument()
    expect(within(findingRow!).getByText('src/handler.py')).toBeInTheDocument()
    expect(within(findingRow!).getByText('L18–L18')).toBeInTheDocument()

    await user.click(inspectButton)
    expect(screen.getByRole('heading', { name: 'Finding Details' })).toBeInTheDocument()
    expect(screen.getByText('Replace dynamic evaluation with explicit parsing.')).toBeInTheDocument()
    expect(screen.getByText('Rule: DANGEROUS_EVAL_EXEC')).toBeInTheDocument()
  })

  it('starts a scan through the existing API and refreshes the displayed data', async () => {
    const user = userEvent.setup()
    renderSecurity()
    await screen.findByRole('heading', { name: 'Security findings' })
    await user.click(screen.getByRole('button', { name: 'Run Security Scan' }))

    expect(api.runScan).toHaveBeenCalledWith('repo-1')
    await waitFor(() => expect(api.listFindings).toHaveBeenCalledTimes(2))
  })

  it('updates finding triage status and filters findings by search', async () => {
    const user = userEvent.setup()
    renderSecurity()
    await screen.findByRole('button', { name: 'Inspect Dynamic evaluation detected' })

    await user.type(screen.getByPlaceholderText('Search title, rule, or file…'), 'handler.py')
    expect(screen.getByRole('button', { name: 'Inspect Dynamic evaluation detected' })).toBeInTheDocument()
    await user.clear(screen.getByPlaceholderText('Search title, rule, or file…'))
    await user.click(screen.getByRole('button', { name: 'Inspect Dynamic evaluation detected' }))
    const selects = screen.getAllByRole('combobox')
    await user.selectOptions(selects[3], 'resolved')

    expect(api.updateFinding).toHaveBeenCalledWith('finding-1', 'resolved')
    await waitFor(() => expect(screen.getAllByText('resolved').length).toBeGreaterThan(0))
  })

  it('shows a meaningful empty state when no scan findings exist', async () => {
    vi.mocked(api.listScans).mockResolvedValue([])
    vi.mocked(api.listFindings).mockResolvedValue({ findings: [], total: 0 })
    renderSecurity()

    expect(await screen.findByText('No security findings')).toBeInTheDocument()
    expect(screen.getByText('Run a security scan to find potential issues')).toBeInTheDocument()
    expect(screen.getByText('No scans yet')).toBeInTheDocument()
  })

  it('renders API errors with an actionable refresh control', async () => {
    vi.mocked(api.listFindings).mockRejectedValue({ message: 'Security service unavailable' })
    renderSecurity()

    expect(await screen.findByRole('alert')).toHaveTextContent('Security service unavailable')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})
