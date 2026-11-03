import { formatDistanceToNow, format } from 'date-fns'

export function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString)
    return formatDistanceToNow(date, { addSuffix: true })
  } catch {
    return 'Unknown'
  }
}

export function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === 'object' && error !== null && 'message' in error) {
    const message = (error as { message?: unknown }).message
    if (typeof message === 'string' && message.trim()) return message
  }
  return fallback
}

export function formatDateTime(dateString: string): string {
  try {
    const date = new Date(dateString)
    return format(date, 'PPp')
  } catch {
    return 'Invalid date'
  }
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical': return 'text-status-danger bg-status-danger/15'
    case 'high': return 'text-status-danger bg-status-danger/15'
    case 'medium': return 'text-status-warning bg-status-warning/15'
    case 'low': return 'text-status-cyan bg-status-cyan/15'
    case 'info': return 'text-text-secondary bg-surface-hover'
    default: return 'text-text-muted bg-surface-hover'
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'completed': return 'text-status-success bg-status-success/15'
    case 'processing': return 'text-status-cyan bg-status-cyan/15'
    case 'queued': return 'text-status-warning bg-status-warning/15'
    case 'failed': return 'text-status-danger bg-status-danger/15'
    case 'indexed': return 'text-status-success bg-status-success/15'
    case 'pending': return 'text-gray-400 bg-gray-500/20'
    default: return 'text-gray-400 bg-gray-500/20'
  }
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength - 3) + '...'
}

export function getLanguageLabel(language: string | null): string {
  if (!language) return 'Unknown'
  const labels: Record<string, string> = {
    python: 'Python',
    javascript: 'JavaScript',
    typescript: 'TypeScript',
    java: 'Java',
    go: 'Go',
    rust: 'Rust',
    cpp: 'C++',
    c: 'C',
    cs: 'C#',
    ruby: 'Ruby',
    php: 'PHP',
    swift: 'Swift',
    kotlin: 'Kotlin',
    scala: 'Scala',
    html: 'HTML',
    css: 'CSS',
    scss: 'SCSS',
    json: 'JSON',
    yaml: 'YAML',
    toml: 'TOML',
    markdown: 'Markdown',
    sql: 'SQL',
    shell: 'Shell',
    dockerfile: 'Dockerfile',
    terraform: 'Terraform',
  }
  return labels[language.toLowerCase()] || language
}
