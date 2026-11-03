import { useEffect, useState, useRef } from 'react'
import { Link, useParams, useNavigate, useLocation } from 'react-router-dom'
import { api } from '../api/client'
import { Repository, Citation } from '../types'
import { Badge, Button } from '../components'
import { getErrorMessage, getLanguageLabel } from '../utils/format'
import { cn } from '../utils/cn'
import {
  Send,
  Loader2,
  FileText,
  Copy,
  AlertCircle,
  Info,
  ChevronLeft,
  X,
  CheckCircle,
} from 'lucide-react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  timestamp: Date
  loading?: boolean
  error?: string
}

export function ChatPage() {
  const { repositoryId } = useParams<{ repositoryId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const uploadCompleted = Boolean((location.state as { uploadCompleted?: boolean } | null)?.uploadCompleted)
  const [repository, setRepository] = useState<Repository | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [sending, setSending] = useState(false)
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)
  const [citationDrawerOpen, setCitationDrawerOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (repositoryId) {
      fetchRepository()
    }
  }, [repositoryId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function fetchRepository() {
    try {
      setLoading(true)
      setLoadError('')
      const repo = await api.getRepository(repositoryId!)
      setRepository(repo)
    } catch (err) {
      console.error(err)
      setLoadError(getErrorMessage(err, 'Could not load this repository.'))
    } finally {
      setLoading(false)
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || sending || !repositoryId) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      citations: [],
      timestamp: new Date(),
    }

    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      citations: [],
      timestamp: new Date(),
      loading: true,
    }

    const question = input.trim()
    setInput('')
    setMessages((prev) => [...prev, userMessage, assistantMessage])
    setSending(true)

    try {
      const response = await api.chat(repositoryId, question)
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessage.id
            ? { ...msg, content: response.answer, citations: response.citations, loading: false }
            : msg
        )
      )
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessage.id
            ? { ...msg, content: '', error: getErrorMessage(err, 'Failed to get a response. Please try again.'), loading: false }
            : msg
        )
      )
    } finally {
      setSending(false)
    }
  }

  function handleCitationClick(citation: Citation) {
    setSelectedCitation(citation)
    setCitationDrawerOpen(true)
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text)
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-accent" />
      </div>
    )
  }

  if (!repository) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-text-muted mx-auto mb-4" />
          <h3 className="text-lg font-medium text-text-primary mb-2">{loadError ? 'Could not open repository' : 'Repository not found'}</h3>
          {loadError && <p className="text-sm text-text-secondary mb-4">{loadError}</p>}
          <Button onClick={() => navigate('/repositories')}>Back to Repositories</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[calc(100dvh-6rem)] min-h-[420px] max-h-[1100px]">
      {/* Repository Header */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 border-b border-surface-border pb-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="h-8 w-8 shrink-0 rounded bg-background-tertiary flex items-center justify-center"><FileText className="h-4 w-4 text-accent" /></div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2"><h1 className="truncate text-base font-semibold text-text-primary">{repository.display_name}</h1><Badge variant={repository.status as any}>{repository.status}</Badge></div>
            <p className="mt-0.5 truncate font-mono text-[10px] text-text-muted">{repository.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-text-muted sm:inline">{repository.file_count.toLocaleString()} files · {repository.chunk_count.toLocaleString()} chunks</span>
          <Link to="/repositories" className="btn-ghost h-8 px-2 text-xs">
            <ChevronLeft className="h-4 w-4" />
            Repositories
          </Link>
        </div>
      </div>

      {uploadCompleted && <div className="mb-3 flex items-start gap-2 border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-100" role="status"><CheckCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300" /><p>ZIP uploaded successfully. Repository status: <strong className="capitalize">{repository.status}</strong>.</p></div>}
      {repository.status !== 'indexed' && <div className="mb-3 flex items-start gap-2 border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-100" role="status"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" /><p>This repository is <strong>{repository.status}</strong>. Code questions are available after indexing completes. <Link to="/repositories" className="ml-1 underline underline-offset-2">View repository status</Link></p></div>}

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] border border-surface-border bg-surface">
      <div className="min-w-0 min-h-0 flex flex-col">
      {/* Investigation transcript */}
      <div className="flex-1 min-h-0 overflow-y-auto space-y-4 p-3 sm:p-4" aria-live="polite">
        {messages.length === 0 && (
          <div className="flex min-h-full flex-col items-center justify-center py-8 text-center">
            <div className="h-9 w-9 rounded border border-surface-border bg-background-tertiary flex items-center justify-center"><Info className="h-4 w-4 text-accent" /></div>
            <h2 className="mt-3 text-sm font-semibold text-text-primary">Start a code investigation</h2>
            <p className="mt-1 max-w-md text-xs leading-relaxed text-text-secondary">Ask a focused question. Answers include source references when matching code is available.</p>
            <div className="mt-5 grid w-full max-w-xl gap-1.5 sm:grid-cols-2">
              {[
                'How is authentication implemented?',
                'What happens when a user uploads a file?',
                'Where is the database connection configured?',
                'Show me the main API routes',
              ].map((q) => (
                <Button
                  key={q}
                  variant="secondary"
                  size="sm"
                  className="h-auto min-h-9 justify-start text-left leading-snug"
                  onClick={() => {
                    setInput(q)
                    inputRef.current?.focus()
                  }}
                >
                  {q}
                </Button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={cn('flex gap-2.5', message.role === 'user' && 'flex-row-reverse', message.loading && 'hidden')}
          >
            <div
              className={cn(
                'mt-0.5 h-6 w-6 rounded flex items-center justify-center flex-shrink-0',
                message.role === 'user'
                  ? 'bg-accent/20 text-accent'
                  : 'bg-surface-border/50 text-text-muted'
              )}
            >
              {message.role === 'user' ? (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              ) : (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 002 2z" />
                </svg>
              )}
            </div>
            <div className={cn('flex-1 min-w-0', message.role === 'user' ? 'text-right' : '')}>
              <div className={cn('inline-block max-w-[92%] px-3 py-2.5 text-left', message.role === 'user' ? 'bg-background-tertiary text-text-primary border border-surface-border' : 'bg-background/60 text-text-primary border border-surface-border/70')}>
                {message.error ? (
                  <div className="flex items-start gap-2 text-red-400">
                    <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">Error</p>
                      <p className="text-sm mt-1">{message.error}</p>
                    </div>
                  </div>
                ) : (
                  <>
                    <AnswerContent content={message.content} onCopy={copyToClipboard} />
                    {message.citations.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-surface-border/50">
                        <p className="text-xs font-medium text-text-muted mb-2">Sources:</p>
                        <div className="flex flex-wrap gap-2">
                          {message.citations.map((citation, idx) => (
                            <button
                              key={`${citation.chunk_id}-${idx}`}
                              onClick={() => handleCitationClick(citation)}
                              className="btn-secondary text-[11px] px-2 py-1 h-auto gap-1 rounded-sm font-mono"
                              aria-label={`Open source ${citation.file_path}, lines ${citation.start_line} to ${citation.end_line}`}
                            >
                              <FileText className="h-3 w-3" />
                              <span>{citation.file_path}:{citation.start_line}-{citation.end_line}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
              <div className={cn('mt-1 flex items-center gap-2 text-[10px] text-text-muted', message.role === 'user' ? 'justify-start' : 'justify-end')}>
                <span>{message.timestamp.toLocaleTimeString()}</span>
                {!message.loading && message.role === 'assistant' && message.content && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(message.content)}
                    className="h-7 px-2 gap-1"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    Copy
                  </Button>
                )}
              </div>
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-surface-border/50 flex items-center justify-center flex-shrink-0">
              <svg className="h-5 w-5 text-text-muted animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 002 2z" />
              </svg>
            </div>
            <div className="bg-surface border border-surface-border rounded-2xl p-4 max-w-[85%]">
              <div className="flex gap-2">
                <Loader2 className="h-4 w-4 text-accent animate-spin" />
                <span className="text-text-secondary self-center">Thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="shrink-0 border-t border-surface-border bg-background-secondary p-3">
        <form onSubmit={handleSend} className="max-w-4xl mx-auto">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit() } }}
              placeholder={repository.status === 'indexed' ? 'Ask about an implementation, flow, or symbol…' : 'Questions are available when indexing completes'}
              className="flex-1 min-h-[42px] max-h-40 px-3 py-2.5 rounded-md bg-background border border-surface-border text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent resize-y transition-colors"
              rows={1}
              disabled={sending || repository.status !== 'indexed'}
            />
            <Button size="sm" type="submit" disabled={sending || !input.trim() || repository.status !== 'indexed'} className="h-10 shrink-0 px-3" aria-label="Send question">
              <Send className="h-4 w-4" />
            </Button>
          </div>
          <p className="mt-1.5 flex justify-between text-[10px] text-text-muted">
            <span>Answers are grounded in indexed source.</span><span>Enter to send · Shift+Enter for a new line</span>
          </p>
        </form>
      </div>

      </div>
      <aside className={cn('min-h-0 border-t lg:border-t-0 lg:border-l border-surface-border bg-background-secondary', citationDrawerOpen ? 'block' : 'hidden lg:block')} aria-label="Source inspection">
        <div className="flex h-10 items-center justify-between border-b border-surface-border px-3">
          <div className="flex items-center gap-2"><FileText className="h-3.5 w-3.5 text-accent" /><span className="text-[10px] font-semibold uppercase tracking-[.12em] text-text-secondary">Source context</span></div>
          {selectedCitation && <Button variant="ghost" size="sm" className="h-7 w-7 p-0" aria-label="Close source context" onClick={() => { setCitationDrawerOpen(false); setSelectedCitation(null) }}><X className="h-3.5 w-3.5" /></Button>}
        </div>
        {selectedCitation ? <div className="p-3">
          <Badge variant="default" className="mb-2">{getLanguageLabel(selectedCitation.language)}</Badge>
          <p className="break-all font-mono text-xs leading-relaxed text-text-primary">{selectedCitation.file_path}</p>
          <p className="mt-1 font-mono text-[10px] text-accent">L{selectedCitation.start_line}–L{selectedCitation.end_line}</p>
          <pre className="code-block mt-3 max-h-[min(60vh,520px)] whitespace-pre-wrap">{selectedCitation.excerpt}</pre>
          {selectedCitation.relevance_score !== null && selectedCitation.relevance_score !== undefined && <p className="mt-2 text-[10px] text-text-muted">Retrieval relevance · {(selectedCitation.relevance_score * 100).toFixed(1)}%</p>}
        </div> : <div className="p-4"><p className="text-xs leading-relaxed text-text-muted">Select a source citation in an answer to inspect its file path, line range, and retrieved excerpt.</p></div>}
      </aside>
      </div>
    </div>
  )
}

function AnswerContent({ content, onCopy }: { content: string; onCopy: (text: string) => void }) {
  const blocks: Array<{ type: 'text' | 'code'; value: string; language?: string }> = []
  const codePattern = /```([^\n`]*)\n([\s\S]*?)```/g
  let cursor = 0
  let match: RegExpExecArray | null
  while ((match = codePattern.exec(content)) !== null) {
    if (match.index > cursor) blocks.push({ type: 'text', value: content.slice(cursor, match.index) })
    blocks.push({ type: 'code', language: match[1].trim() || 'code', value: match[2].replace(/\n$/, '') })
    cursor = match.index + match[0].length
  }
  if (cursor < content.length || blocks.length === 0) blocks.push({ type: 'text', value: content.slice(cursor) })

  return <div className="space-y-2 text-sm leading-relaxed">
    {blocks.map((block, index) => block.type === 'text'
      ? <p key={`text-${index}`} className="whitespace-pre-wrap">{block.value}</p>
      : <div key={`code-${index}`} className="overflow-hidden border border-surface-border rounded-md bg-background">
          <div className="flex items-center justify-between border-b border-surface-border px-2.5 py-1"><span className="font-mono text-[10px] text-text-muted">{block.language}</span><button type="button" onClick={() => onCopy(block.value)} className="inline-flex items-center gap-1 text-[10px] text-text-muted hover:text-text-primary" aria-label="Copy code"><Copy className="h-3 w-3" />Copy</button></div>
          <pre className="max-h-[420px] overflow-auto p-3 font-mono text-xs leading-5 text-text-secondary"><code>{block.value}</code></pre>
        </div>)}
  </div>
}
