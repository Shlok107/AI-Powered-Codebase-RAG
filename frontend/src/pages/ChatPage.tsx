import { useEffect, useState, useRef } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Repository, Citation } from '../types'
import { Card, Badge, Button, Modal } from '../components'
import { getLanguageLabel } from '../utils/format'
import { cn } from '../utils/cn'
import {
  Send,
  Loader2,
  FileText,
  Copy,
  AlertCircle,
  Info,
  ChevronLeft,
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
  const [repository, setRepository] = useState<Repository | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
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
      const repo = await api.getRepository(repositoryId!)
      setRepository(repo)
    } catch (err) {
      console.error(err)
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
            ? { ...msg, content: '', error: err.message || 'Failed to get response', loading: false }
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
          <h3 className="text-lg font-medium text-text-primary mb-2">Repository not found</h3>
          <Button onClick={() => navigate('/repositories')}>Back to Repositories</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Repository Header */}
      <Card padding="md" className="mb-4">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div className="p-2 bg-accent/10 rounded-lg">
              <FileText className="h-6 w-6 text-accent" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-text-primary">{repository.display_name}</h2>
              <div className="flex items-center gap-2 mt-1 text-sm text-text-muted">
                <Badge variant={repository.status as any} className="gap-1">
                  {repository.status.charAt(0).toUpperCase() + repository.status.slice(1)}
                </Badge>
                {repository.detected_languages.length > 0 && (
                  <>
                    {repository.detected_languages.slice(0, 3).map((lang) => (
                      <Badge key={lang} variant="default" className="text-xs">
                        {getLanguageLabel(lang)}
                      </Badge>
                    ))}
                    {repository.detected_languages.length > 3 && (
                      <Badge variant="default" className="text-xs">
                        +{repository.detected_languages.length - 3} more
                      </Badge>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
          <Link to="/repositories" className="btn-ghost">
            <ChevronLeft className="h-4 w-4" />
            Back
          </Link>
        </div>
      </Card>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto space-y-6 p-4 pb-20">
        {messages.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-center">
            <Info className="h-16 w-16 text-text-muted mb-6" />
            <h3 className="text-xl font-medium text-text-primary mb-2">Start a conversation</h3>
            <p className="text-text-secondary max-w-md mb-8">
              Ask questions about this repository. Answers are grounded in the codebase with citations to source files.
            </p>
            <div className="grid gap-2 sm:grid-cols-2 max-w-md">
              {[
                'How is authentication implemented?',
                'What happens when a user uploads a file?',
                'Where is the database connection configured?',
                'Show me the main API routes',
              ].map((q) => (
                <Button
                  key={q}
                  variant="secondary"
                  className="text-left justify-start h-auto py-3"
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
            className={cn('flex gap-3', message.role === 'user' && 'flex-row-reverse')}
          >
            <div
              className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
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
              <div className={cn('inline-block max-w-[85%] p-4 rounded-2xl', message.role === 'user' ? 'bg-accent/10 text-text-primary' : 'bg-surface border border-surface-border')}>
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
                    <div className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</div>
                    {message.citations.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-surface-border/50">
                        <p className="text-xs font-medium text-text-muted mb-2">Sources:</p>
                        <div className="flex flex-wrap gap-2">
                          {message.citations.map((citation, idx) => (
                            <button
                              key={`${citation.chunk_id}-${idx}`}
                              onClick={() => handleCitationClick(citation)}
                              className="btn-secondary text-xs px-2 py-1 h-auto gap-1"
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
              <div className="mt-1 flex items-center justify-end gap-2 text-xs text-text-muted">
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
      <div className="fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-md border-t border-surface-border p-4 lg:ml-64 lg:fixed lg:bottom-0">
        <form onSubmit={handleSend} className="max-w-4xl mx-auto">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about the codebase..."
              className="flex-1 min-h-[48px] max-h-48 px-4 py-3 rounded-xl bg-surface border border-surface-border text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent resize-none transition-all"
              rows={1}
              disabled={sending}
            />
            <Button type="submit" disabled={sending || !input.trim()} className="h-12 shrink-0">
              <Send className="h-4 w-4" />
            </Button>
          </div>
          <p className="text-xs text-text-muted mt-2 text-center">
            Press Enter to send • Shift+Enter for new line
          </p>
        </form>
      </div>

      {/* Citation Drawer */}
      <Modal
        isOpen={citationDrawerOpen}
        onClose={() => setCitationDrawerOpen(false)}
        title="Source Code"
        size="lg"
      >
        {selectedCitation && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-accent" />
                <div>
                  <p className="font-medium text-text-primary">{selectedCitation.file_path}</p>
                  <p className="text-sm text-text-secondary">Lines {selectedCitation.start_line}–{selectedCitation.end_line}</p>
                </div>
              </div>
              <Badge variant={selectedCitation.language as any}>{getLanguageLabel(selectedCitation.language)}</Badge>
            </div>
            <pre className="code-block whitespace-pre-wrap text-sm">{selectedCitation.excerpt}</pre>
            {selectedCitation.relevance_score && (
              <p className="text-xs text-text-muted">Relevance: {(selectedCitation.relevance_score * 100).toFixed(1)}%</p>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}