import type { Repository, SecurityFinding, SecurityScan } from '../types'

const timestamps = {
  created_at: '2026-11-01T10:00:00.000Z',
  updated_at: '2026-11-02T10:00:00.000Z',
}

export function makeRepository(overrides: Partial<Repository> = {}): Repository {
  return {
    id: 'repo-1',
    display_name: 'payments-service',
    source_type: 'zip_upload',
    source_metadata: { original_filename: 'payments-service.zip' },
    status: 'indexed',
    detected_languages: ['python', 'typescript'],
    file_count: 12,
    chunk_count: 26,
    error_summary: null,
    indexed_at: '2026-11-02T09:00:00.000Z',
    ...timestamps,
    ...overrides,
  }
}

export function makeScan(overrides: Partial<SecurityScan> = {}): SecurityScan {
  return {
    id: 'scan-1',
    repository_id: 'repo-1',
    status: 'completed',
    findings_count: 1,
    critical_count: 0,
    high_count: 1,
    medium_count: 0,
    low_count: 0,
    info_count: 0,
    error_summary: null,
    started_at: '2026-11-02T09:00:00.000Z',
    completed_at: '2026-11-02T09:00:01.000Z',
    ...timestamps,
    ...overrides,
  }
}

export function makeFinding(overrides: Partial<SecurityFinding> = {}): SecurityFinding {
  return {
    id: 'finding-1',
    scan_id: 'scan-1',
    repository_id: 'repo-1',
    rule_id: 'DANGEROUS_EVAL_EXEC',
    title: 'Dynamic evaluation detected',
    category: 'dangerous_code',
    severity: 'high',
    confidence: 'high',
    file_path: 'src/handler.py',
    start_line: 18,
    end_line: 18,
    redacted_evidence: 'eval(user_input)',
    explanation: 'The code evaluates a value that may be controlled by a caller.',
    remediation: 'Replace dynamic evaluation with explicit parsing.',
    references: [],
    status: 'open',
    content_hash: 'e'.repeat(64),
    ...timestamps,
    ...overrides,
  }
}
