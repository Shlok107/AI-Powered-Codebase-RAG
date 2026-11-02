import { formatDistanceToNow, format } from 'date-fns'

export function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString)
    return formatDistanceToNow(date, { addSuffix: true })
  } catch {
    return 'Unknown'
  }
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
    case 'critical': return 'text-red-400 bg-red-500/20'
    case 'high': return 'text-orange-400 bg-orange-500/20'
    case 'medium': return 'text-yellow-400 bg-yellow-500/20'
    case 'low': return 'text-green-400 bg-green-500/20'
    case 'info': return 'text-blue-400 bg-blue-500/20'
    default: return 'text-gray-400 bg-gray-500/20'
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'completed': return 'text-green-400 bg-green-500/20'
    case 'processing': return 'text-blue-400 bg-blue-500/20'
    case 'queued': return 'text-yellow-400 bg-yellow-500/20'
    case 'failed': return 'text-red-400 bg-red-500/20'
    case 'indexed': return 'text-green-400 bg-green-500/20'
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