export interface Repository {
  id: string
  display_name: string
  source_type: 'zip_upload' | 'git_url'
  source_metadata: Record<string, unknown>
  status: 'pending' | 'processing' | 'indexed' | 'failed'
  detected_languages: string[]
  file_count: number
  chunk_count: number
  error_summary: string | null
  indexed_at: string | null
  created_at: string
  updated_at: string
}

export interface File {
  id: string
  repository_id: string
  relative_path: string
  language: string | null
  size_bytes: number
  content_hash: string
  line_count: number
  indexing_status: string
  skip_reason: string | null
  created_at: string
  updated_at: string
}

export interface FileContentResponse {
  path: string
  language: string | null
  content: string
  start_line: number
  end_line: number
  total_lines: number
}

export interface Chunk {
  id: string
  repository_id: string
  file_id: string
  start_line: number
  end_line: number
  language: string | null
  chunk_type: string | null
  content_hash: string
  text: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  repository_id: string
  job_type: 'indexing' | 'security_scan'
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
  total_items: number
  processed_items: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface Citation {
  chunk_id: string
  file_path: string
  start_line: number
  end_line: number
  language: string | null
  relevance_score: number | null
  excerpt: string
}

export interface ChatResponse {
  answer: string
  citations: Citation[]
  conversation_id: string
  model_used: string | null
  retrieval_time_ms: number | null
  generation_time_ms: number | null
}

export interface Conversation {
  id: string
  repository_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  created_at: string
}

export interface SecurityScan {
  id: string
  repository_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  findings_count: number
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  info_count: number
  error_summary: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface SecurityFinding {
  id: string
  scan_id: string
  repository_id: string
  rule_id: string
  title: string
  category: 'secrets' | 'dangerous_code' | 'dependencies' | 'infrastructure' | 'configuration'
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  confidence: 'high' | 'medium' | 'low'
  file_path: string | null
  start_line: number | null
  end_line: number | null
  redacted_evidence: string | null
  explanation: string
  remediation: string
  references: string[]
  status: 'open' | 'dismissed' | 'resolved'
  content_hash: string
  created_at: string
  updated_at: string
}

export interface FindingFilter {
  severity?: string[]
  category?: string[]
  file_path?: string
  status?: string[]
  rule_id?: string
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  version: string
  database: 'connected' | 'disconnected'
  llm_provider: 'configured' | 'unconfigured'
  embedding_provider: 'configured' | 'unconfigured'
  timestamp: string
}

export interface DependencyGraphNode {
  id: string
  type: 'file'
  label: string
  path: string
  language: string
  degree: number
  x: number
  y: number
}

export interface DependencyGraphEdge {
  source: string
  target: string
  type: 'imports'
  source_lines: number[]
}

export interface DependencyGraphResponse {
  repository_id: string
  repository_name: string
  nodes: DependencyGraphNode[]
  edges: DependencyGraphEdge[]
  files_analyzed: number
  python_files: number
  resolved_relationships: number
  parse_errors: number
  truncated: boolean
  coverage: { languages: string[]; relationship_types: string[]; partial: boolean }
}

export interface DependencyNodeDetails {
  repository_id: string
  depth: number
  node: DependencyGraphNode
  direct_dependencies: string[]
  direct_dependents: string[]
  dependencies: string[]
  dependents: string[]
  dependency_count: number
  dependent_count: number
}

export interface DependencyImpactResponse {
  repository_id: string
  node_id: string
  depth: number
  affected_dependents: string[]
  direct_dependents: string[]
}

export interface ApiError {
  code: string
  message: string
  details: Record<string, unknown>
}
