import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Card, CardHeader, CardTitle, CardContent, Badge, Input } from '../components'
import { formatRelativeTime } from '../utils/format'
import { cn } from '../utils/cn'
import {
  Settings,
  Database,
  MessageSquare,
  FileCode,
  Shield,
  RefreshCw,
  Info,
} from 'lucide-react'

interface HealthStatus {
  status: string
  database: string
  llm_provider: string
  embedding_provider: string
  version?: string
  timestamp?: string
}

export function SettingsPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHealth()
  }, [])

  async function fetchHealth() {
    try {
      setLoading(true)
      const res = await api.health()
      setHealth(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'connected':
      case 'configured':
      case 'healthy':
        return <Badge variant="success">{status.charAt(0).toUpperCase() + status.slice(1)}</Badge>
      case 'degraded':
        return <Badge variant="warning">Degraded</Badge>
      default:
        return <Badge variant="critical">{status.charAt(0).toUpperCase() + status.slice(1)}</Badge>
    }
  }

  return (
    <div className="space-y-6 animate-in max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Settings</h1>
        <p className="text-text-secondary mt-1">Configure providers, integrations, and preferences</p>
      </div>

      {/* System Health */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            System Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-8 w-8 animate-spin text-accent" />
            </div>
          ) : health ? (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-4">
                <div className="flex items-center gap-3 p-3 bg-surface-border/50 rounded-lg">
                  <Database className={cn('h-5 w-5', health.database === 'connected' ? 'text-green-400' : 'text-red-400')} />
                  <div>
                    <p className="text-sm font-medium text-text-primary">Database</p>
                    <p className="text-xs text-text-secondary">{getStatusBadge(health.database)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-surface-border/50 rounded-lg">
                  <MessageSquare className={cn('h-5 w-5', health.llm_provider === 'configured' ? 'text-green-400' : 'text-yellow-400')} />
                  <div>
                    <p className="text-sm font-medium text-text-primary">LLM Provider</p>
                    <p className="text-xs text-text-secondary">{getStatusBadge(health.llm_provider)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-surface-border/50 rounded-lg">
                  <FileCode className={cn('h-5 w-5', health.embedding_provider === 'configured' ? 'text-green-400' : 'text-yellow-400')} />
                  <div>
                    <p className="text-sm font-medium text-text-primary">Embeddings</p>
                    <p className="text-xs text-text-secondary">{getStatusBadge(health.embedding_provider)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-surface-border/50 rounded-lg">
                  <Shield className={cn('h-5 w-5', health.status === 'healthy' ? 'text-green-400' : health.status === 'degraded' ? 'text-yellow-400' : 'text-red-400')} />
                  <div>
                    <p className="text-sm font-medium text-text-primary">Overall Health</p>
                    <p className="text-xs text-text-secondary capitalize">{getStatusBadge(health.status)}</p>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-surface-border">
                <h4 className="text-sm font-medium text-text-secondary mb-3">Configuration</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-text-secondary">API Version</span>
                    <span className="text-text-primary font-mono">{health.version}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-secondary">Last Checked</span>
                    <span className="text-text-primary">{formatRelativeTime(health.timestamp || '')}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-text-secondary">Failed to load system status</p>
          )}
        </CardContent>
      </Card>

      {/* Provider Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Provider Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div>
              <h4 className="font-medium text-text-primary mb-3">LLM Provider (OpenAI Compatible)</h4>
              <div className="space-y-3">
                <p className="text-sm text-text-secondary">
                  Configure an OpenAI-compatible chat completion endpoint for AI-powered code Q&A.
                  This can be a local model server (Ollama, vLLM, etc.) or a cloud provider.
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="Base URL"
                    placeholder="https://api.openai.com/v1"
                    helperText="OpenAI-compatible API base URL"
                  />
                  <Input
                    label="API Key"
                    type="password"
                    placeholder="sk-..."
                    helperText="API key for authentication"
                  />
                  <Input
                    label="Model"
                    placeholder="gpt-4, nemotron-3-ultra, etc."
                    helperText="Model identifier"
                  />
                </div>
                <p className="text-xs text-text-muted mt-2">
                  Set LLM_PROVIDER=openai_compatible, LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in your .env file.
                </p>
              </div>
            </div>

            <div className="pt-6 border-t border-surface-border">
              <h4 className="font-medium text-text-primary mb-3">Embedding Provider</h4>
              <div className="space-y-3">
                <p className="text-sm text-text-secondary">
                  Configure embeddings for semantic search. Supports OpenAI-compatible APIs or local sentence-transformers.
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="Provider"
                    placeholder="sentence_transformers or openai_compatible"
                    helperText="Embedding provider type"
                  />
                  <Input
                    label="Model"
                    placeholder="sentence-transformers/all-MiniLM-L6-v2"
                    helperText="Model identifier"
                  />
                  <Input
                    label="Base URL (if OpenAI compatible)"
                    placeholder="https://api.openai.com/v1"
                  />
                  <Input
                    label="Dimensions"
                    type="number"
                    placeholder="384"
                    helperText="Vector dimensions (384 for MiniLM)"
                  />
                </div>
                <p className="text-xs text-text-muted mt-2">
                  Set EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_BASE_URL, and EMBEDDING_DIMENSIONS in your .env file.
                </p>
              </div>
            </div>

            <div className="pt-6 border-t border-surface-border">
              <h4 className="font-medium text-text-primary mb-3">AWS Configuration (Optional)</h4>
              <p className="text-sm text-text-secondary mb-3">
                For cloud deployment with ECS, S3, RDS, and SQS.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label="AWS Region" placeholder="us-east-1" />
                <Input label="S3 Bucket" placeholder="my-codebase-rag-bucket" />
                <Input label="SQS Queue URL" placeholder="https://sqs.us-east-1.amazonaws.com/..." />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Application Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Application Limits</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Max Upload (MB)" type="number" placeholder="50" />
            <Input label="Max Archive Files" type="number" placeholder="10000" />
            <Input label="Max Uncompressed (MB)" type="number" placeholder="300" />
            <Input label="Max Single File (MB)" type="number" placeholder="5" />
            <Input label="Chunk Size" type="number" placeholder="1200" />
            <Input label="Chunk Overlap" type="number" placeholder="150" />
            <Input label="Retrieval Top-K" type="number" placeholder="6" />
          </div>
          <p className="text-xs text-text-muted mt-4">
            These values are configured via environment variables. See .env.example for all options.
          </p>
        </CardContent>
      </Card>

      {/* Information */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Info className="h-5 w-5" />
            About
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <p className="text-text-secondary">
              <strong>Codebase RAG</strong> is a codebase intelligence and security analysis platform.
              It combines repository ingestion, code-aware chunking, embeddings, vector search,
              grounded LLM answers, and deterministic security checks.
            </p>
            <p className="text-text-secondary">
              <strong>Version:</strong> 0.1.0 (MVP)
            </p>
            <p className="text-text-secondary">
              <strong>Tech Stack:</strong> FastAPI, PostgreSQL/pgvector, React, TypeScript, Tailwind CSS
            </p>
            <p className="text-text-muted">
              Security findings are advisory and not a substitute for comprehensive security review.
              The tool does not guarantee absence of vulnerabilities.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}