import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Send, Plus, Bot, Paperclip, MessageSquare, Clock,
  Search, AlertCircle, Zap, BookOpen, ChevronDown,
  ChevronUp, Database, ToggleLeft, ToggleRight,
  X, CheckCircle, Info, Filter, FileText, Loader2, Trash2, RefreshCw
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { Avatar } from '../../components/ui/Avatar'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'
import {
  sendRAGMessage, sendChatMessage, parseChatFile,
  fetchConversations, fetchMessages,
  createConversation, deleteConversation, appendMessage,
  generateConversationTitle,
} from '../../services/chatService'
import { PDFCitationViewerModal } from '../../components/documents/PDFCitationViewerModal'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

/** Normalise a backend message row to the shape the UI expects */
function normaliseMessage(msg) {
  return {
    id:           msg.id,
    role:         msg.role,
    content:      msg.content,
    timestamp:    msg.created_at || new Date().toISOString(),
    citations:    Array.isArray(msg.sources) ? msg.sources : [],
    ragEnabled:   Array.isArray(msg.sources) && msg.sources.length > 0,
    model:        msg.model || null,
    processingTime: msg.processing_time || null,
    usedFallback: false,
    attachments:  [],
  }
}

// ── Typing indicator ──────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="flex items-end gap-2 mb-4">
      <div className="w-7 h-7 rounded-full bg-primary-600 flex items-center justify-center flex-shrink-0">
        <Bot size={14} className="text-white" />
      </div>
      <div className="bg-surface-100 rounded-2xl rounded-bl-sm px-4 py-3 border border-surface-200">
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="w-2 h-2 rounded-full bg-surface-400"
              animate={{ y: [0, -4, 0] }}
              transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Citations panel ────────────────────────────────────────────
function CitationsPanel({ citations, usedFallback, onCitationClick }) {
  const [open, setOpen] = useState(false)

  if (usedFallback) {
    return (
      <div className="mt-2 flex items-center gap-1.5 text-[11px] text-amber-500 bg-amber-500/10 border border-amber-500/20 rounded-lg px-2.5 py-1.5">
        <Info size={11} className="flex-shrink-0" />
        <span>No matching documents found — answered from general knowledge</span>
      </div>
    )
  }

  if (!citations || citations.length === 0) return null

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[11px] text-primary-400 hover:text-primary-300 font-medium transition-colors"
      >
        <BookOpen size={11} />
        {citations.length} source{citations.length !== 1 ? 's' : ''} used
        {open ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-1.5">
              {citations.map((c) => (
                <div
                  key={c.source_index}
                  onClick={() => onCitationClick && onCitationClick(c)}
                  className="group flex items-start gap-2.5 bg-surface-200/80 hover:bg-surface-200 border border-surface-300/80 hover:border-primary-500/40 rounded-xl px-3 py-2 cursor-pointer transition-all duration-150 shadow-sm hover:shadow-md"
                  title="Click to open PDF & highlight cited source text"
                >
                  <span className="text-[10px] font-bold text-primary-400 bg-primary-400/10 group-hover:bg-primary-400/20 border border-primary-400/20 rounded px-1.5 py-0.5 flex-shrink-0 mt-0.5 transition-colors">
                    [{c.source_index}]
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1.5">
                      <div className="flex items-center gap-1.5 truncate">
                        <span className="text-xs font-semibold text-surface-800 group-hover:text-primary-300 transition-colors truncate">
                          {c.file_name}
                        </span>
                        {(c.page_number || c.page) && (
                          <span className="text-[10px] font-medium text-surface-500 bg-surface-300/40 px-1 rounded">
                            p.{c.page_number || c.page}
                          </span>
                        )}
                        {Array.isArray(c.evidence_spans) && c.evidence_spans.length > 1 && (
                          <span className="text-[10px] font-medium text-amber-400/90 bg-amber-500/10 border border-amber-500/20 px-1 rounded">
                            {c.evidence_spans.length} passages
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-primary-400 opacity-0 group-hover:opacity-100 font-medium transition-opacity flex items-center gap-0.5 flex-shrink-0">
                        View PDF &rarr;
                      </span>
                    </div>
                    <p className="text-[11px] text-surface-500 group-hover:text-surface-400 mt-0.5 line-clamp-2 transition-colors">
                      {c.source_text || c.text_preview || c.full_text}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Markdown renderer (dark-mode safe) ───────────────────────
function renderContent(content) {
  const lines = content.split('\n')
  const elements = []
  let listItems = []

  const flushList = (key) => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${key}`} className="list-disc ml-5 my-1.5 space-y-1 text-surface-700">
          {listItems}
        </ul>
      )
      listItems = []
    }
  }

  const formatInline = (text) => {
    // Only handle bold — Gemini no longer inlines [Source N] citations
    return text.replace(/\*\*(.*?)\*\*/g, '<strong style="font-weight:600;color:inherit;">$1</strong>')
  }

  lines.forEach((line, i) => {
    const trimmed = line.trim()

    if (!trimmed) {
      flushList(i)
      elements.push(<div key={`sp-${i}`} className="h-1" />)
      return
    }

    // Headings
    if (/^#{1,3}\s/.test(trimmed)) {
      flushList(i)
      const text = trimmed.replace(/^#+\s/, '')
      elements.push(
        <p key={i} className="font-semibold text-surface-900 mt-2 mb-0.5 text-sm"
          dangerouslySetInnerHTML={{ __html: formatInline(text) }} />
      )
      return
    }

    // Bullets: *, -, •
    const bulletMatch = trimmed.match(/^[\*\-•]\s+(.+)/)
    if (bulletMatch) {
      listItems.push(
        <li key={i} className="text-surface-700"
          dangerouslySetInnerHTML={{ __html: formatInline(bulletMatch[1]) }} />
      )
      return
    }

    // Numbered lists: 1. text
    if (/^\d+\.\s+/.test(trimmed)) {
      flushList(i)
      elements.push(
        <p key={i} className="mb-0.5 ml-1 text-surface-700"
          dangerouslySetInnerHTML={{ __html: formatInline(trimmed) }} />
      )
      return
    }

    // Regular paragraph
    flushList(i)
    elements.push(
      <p key={i} className="mb-1 last:mb-0 text-surface-700"
        dangerouslySetInnerHTML={{ __html: formatInline(trimmed) }} />
    )
  })

  flushList('end')
  return elements
}

// ── Message bubble ────────────────────────────────────────────
function MessageBubble({ msg, userName, userAvatar, onCitationClick }) {
  const isUser = msg.role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex items-end gap-2 mb-4 ${isUser ? 'flex-row-reverse' : ''}`}
    >
      {isUser ? (
        <Avatar src={userAvatar} name={userName} size="xs" />
      ) : (
        <div className="w-7 h-7 rounded-full bg-primary-600 flex items-center justify-center flex-shrink-0">
          <Bot size={14} className="text-white" />
        </div>
      )}

      <div className={`max-w-[78%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? 'bg-primary-600 text-white rounded-br-sm'
            : 'bg-surface-100 border border-surface-200 rounded-bl-sm shadow-sm'
        }`}>
          {isUser ? (
            <div className="space-y-1.5">
              {msg.attachments && msg.attachments.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pb-1">
                  {msg.attachments.map((att, idx) => (
                    <div
                      key={idx}
                      className="inline-flex items-center gap-1.5 bg-white/20 backdrop-blur-sm border border-white/30 rounded-lg px-2.5 py-1 text-xs text-white"
                    >
                      <Paperclip size={12} className="text-white/80" />
                      <span className="font-medium truncate max-w-[200px]">{att.filename}</span>
                      {att.file_type && (
                        <span className="text-[10px] text-white/70 bg-white/10 px-1 rounded">
                          {att.file_type}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <p className="text-white">{msg.content}</p>
            </div>
          ) : (
            renderContent(msg.content)
          )}
        </div>

        {/* Metadata row */}
        <div className="flex items-center gap-2 mt-1 px-1">
          <span className="text-[11px] text-surface-500">
            {new Date(msg.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
          </span>
          {msg.ragEnabled && (
            <span className="text-[10px] text-primary-400 flex items-center gap-0.5">
              <Database size={9} /> RAG
            </span>
          )}
          {msg.model && (
            <span className="text-[10px] text-surface-500 flex items-center gap-0.5">
              <Zap size={9} />Enterprise AI
            </span>
          )}
          {msg.processingTime && (
            <span className="text-[10px] text-surface-500">{msg.processingTime}s</span>
          )}
        </div>

        {/* Citations (AI messages only) */}
        {!isUser && (
          <div className="w-full px-1">
            <CitationsPanel
              citations={msg.citations}
              usedFallback={msg.usedFallback}
              onCitationClick={onCitationClick}
            />
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ── Document Knowledge Base Selector Panel ────────────────────
function ChatDocumentSelectorPanel({
  selectedIds,
  onToggle,
  onSelectAll,
  onClear,
  onClose,
  allDocs,
  loadingDocs,
}) {
  const [scopeTab, setScopeTab] = useState('all') // 'all' | 'company' | 'workspace'
  const [search, setSearch] = useState('')

  const filteredDocs = allDocs.filter((d) => {
    const matchesScope =
      scopeTab === 'all'
        ? true
        : scopeTab === 'company'
        ? d.scope === 'company'
        : d.scope === 'workspace'
    const matchesSearch =
      d.file_name.toLowerCase().includes(search.toLowerCase()) ||
      (d.category && d.category.toLowerCase().includes(search.toLowerCase()))
    return matchesScope && matchesSearch
  })

  const companyCount = allDocs.filter((d) => d.scope === 'company').length
  const workspaceCount = allDocs.filter((d) => d.scope === 'workspace').length

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="bg-surface-100/90 backdrop-blur-sm border-b border-surface-200 px-6 py-4 space-y-3 flex-shrink-0 z-20 shadow-md"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-primary-600/15 border border-primary-500/20 flex items-center justify-center">
            <BookOpen size={15} className="text-primary-400" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-surface-900 flex items-center gap-1.5">
              Knowledge Base Documents
              <span className="text-[10px] text-primary-400 bg-primary-600/15 border border-primary-500/20 px-2 py-0.5 rounded-md">
                {allDocs.length} Indexed
              </span>
            </h4>
            <p className="text-[11px] text-surface-500">
              Select specific documents to ground AI chat queries (or leave unselected to search all)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {filteredDocs.length > 0 && (
            <button
              onClick={() => onSelectAll(filteredDocs.map((d) => d.id))}
              className="text-[11px] font-semibold text-primary-400 hover:text-primary-300 bg-primary-600/10 hover:bg-primary-600/20 border border-primary-500/30 rounded-lg px-3 py-1 transition-all"
            >
              Select All ({filteredDocs.length})
            </button>
          )}
          {selectedIds.length > 0 && (
            <button
              onClick={onClear}
              className="text-[11px] font-semibold text-surface-400 hover:text-surface-200 bg-surface-200 hover:bg-surface-300 rounded-lg px-3 py-1 transition-all"
            >
              Clear Selection ({selectedIds.length})
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-surface-400 hover:text-surface-700 hover:bg-surface-200 transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Tabs & Search bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap pt-1">
        <div className="flex items-center gap-1 bg-surface-200 p-1 rounded-xl">
          <button
            onClick={() => setScopeTab('all')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
              scopeTab === 'all'
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-surface-600 hover:text-surface-900 hover:bg-surface-300/40'
            }`}
          >
            All ({allDocs.length})
          </button>
          <button
            onClick={() => setScopeTab('company')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
              scopeTab === 'company'
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-surface-600 hover:text-surface-900 hover:bg-surface-300/40'
            }`}
          >
            🏢 Company Knowledge ({companyCount})
          </button>
          <button
            onClick={() => setScopeTab('workspace')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
              scopeTab === 'workspace'
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-surface-600 hover:text-surface-900 hover:bg-surface-300/40'
            }`}
          >
            🔒 My Workspace ({workspaceCount})
          </button>
        </div>

        <div className="relative flex-1 min-w-[220px] max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter documents by name..."
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-surface-200 border border-surface-300 rounded-xl outline-none focus:border-primary-500/50 text-surface-900 placeholder:text-surface-400 transition-all"
          />
        </div>
      </div>

      {/* Document cards grid */}
      <div className="max-h-52 overflow-y-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 pt-1">
        {loadingDocs ? (
          <div className="col-span-full py-6 text-center text-xs text-surface-400 flex items-center justify-center gap-2">
            <Loader2 size={14} className="animate-spin text-primary-400" />
            Loading knowledge base documents...
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="col-span-full py-6 text-center text-xs text-surface-400">
            No indexed documents match the search criteria.
          </div>
        ) : (
          filteredDocs.map((doc) => {
            const isSelected = selectedIds.includes(doc.id)
            return (
              <button
                key={doc.id}
                onClick={() => onToggle(doc.id)}
                className={`flex items-center justify-between p-2.5 rounded-xl border text-left transition-all ${
                  isSelected
                    ? 'bg-primary-600/20 border-primary-500/60 ring-1 ring-primary-500/40'
                    : 'bg-surface-200/80 border-surface-300 hover:border-primary-500/40 hover:bg-surface-200'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0 pr-2">
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 font-bold text-xs ${
                      doc.scope === 'company'
                        ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                        : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                    }`}
                  >
                    <FileText size={13} />
                  </div>
                  <div className="min-w-0">
                    <p
                      className={`text-xs font-semibold truncate ${
                        isSelected ? 'text-primary-300 font-bold' : 'text-surface-900'
                      }`}
                    >
                      {doc.file_name}
                    </p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="text-[10px] font-medium text-surface-400">
                        {doc.scope === 'company' ? '🏢 Company' : '🔒 Workspace'}
                      </span>
                      <span className="text-[10px] text-surface-400">• {doc.category}</span>
                    </div>
                  </div>
                </div>

                <div
                  className={`w-4 h-4 rounded-md border flex items-center justify-center flex-shrink-0 transition-colors ${
                    isSelected
                      ? 'bg-primary-600 border-primary-600 text-white'
                      : 'border-surface-400 bg-surface-300/50'
                  }`}
                >
                  {isSelected && <CheckCircle size={12} className="text-white" />}
                </div>
              </button>
            )
          })
        )}
      </div>
    </motion.div>
  )
}

// ── RAG toggle ────────────────────────────────────────────────
function RAGToggle({ enabled, onToggle }) {
  return (
    <button
      onClick={onToggle}
      title={enabled ? 'RAG enabled — answers use your documents' : 'RAG disabled — direct AI'}
      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all ${
        enabled
          ? 'bg-primary-600/20 border-primary-500/40 text-primary-300'
          : 'bg-surface-100 border-surface-200 text-surface-500 hover:border-surface-300'
      }`}
    >
      {enabled
        ? <ToggleRight size={14} className="text-primary-400" />
        : <ToggleLeft size={14} />
      }
      <Database size={12} />
      {enabled ? 'Docs ON' : 'Docs OFF'}
    </button>
  )
}

// ── Error banner ──────────────────────────────────────────────
function ErrorBanner({ message, onDismiss }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="mx-4 mb-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 flex items-start gap-2"
    >
      <AlertCircle size={15} className="text-red-400 flex-shrink-0 mt-0.5" />
      <p className="text-xs text-red-300 flex-1">{message}</p>
      <button onClick={onDismiss} className="text-red-400 hover:text-red-300">
        <X size={13} />
      </button>
    </motion.div>
  )
}

// ── Main ChatPage ─────────────────────────────────────────────
export function ChatPage() {
  const { user, getUserDisplayName, getUserAvatar } = useAuth()
  const { conversationId: urlConvId } = useParams()
  const navigate = useNavigate()

  // ── Conversation + message state ──────────────────────────────
  const [conversations, setConversations]     = useState([])
  const [selectedConvId, setSelectedConvId]   = useState(null)
  const [messages, setMessages]               = useState([])
  const [loadingConvs, setLoadingConvs]       = useState(false)
  const [loadingMsgs, setLoadingMsgs]         = useState(false)
  const [convError, setConvError]             = useState(null)
  const [convToDelete, setConvToDelete]       = useState(null)
  const [isDeletingConv, setIsDeletingConv]   = useState(false)

  // ── Input / typing ────────────────────────────────────────────
  const [input, setInput]           = useState('')
  const [isTyping, setIsTyping]     = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [error, setError]           = useState(null)

  // ── Citations & PDF Viewer ──────────────────────────────────
  const [selectedCitation, setSelectedCitation] = useState(null)

  // ── RAG / doc controls ────────────────────────────────────────
  const [ragEnabled, setRagEnabled]             = useState(true)
  const [selectedDocIds, setSelectedDocIds]     = useState([])
  const [availableDocs, setAvailableDocs]       = useState([])
  const [loadingAvailableDocs, setLoadingAvailableDocs] = useState(true)
  const [isDocPanelOpen, setIsDocPanelOpen]     = useState(false)

  // ── File attachment ───────────────────────────────────────────
  const [attachments, setAttachments] = useState([])
  const [parsingFile, setParsingFile] = useState(false)

  const messagesEndRef = useRef(null)
  const inputRef       = useRef(null)
  const fileInputRef   = useRef(null)
  const skipFetchConvIdRef = useRef(null)

  const selectedConv = conversations.find((c) => c.id === selectedConvId) || null
  const filteredConvs = conversations.filter(
    (c) => (c.title || '').toLowerCase().includes(searchQuery.toLowerCase())
  )

  // ── Load conversation list on mount ───────────────────────────
  const loadConversations = useCallback(async () => {
    if (!user?.id) return
    setLoadingConvs(true)
    setConvError(null)
    try {
      const data = await fetchConversations(user.id)
      setConversations(data.conversations || [])
    } catch (err) {
      setConvError(err.message || 'Failed to load conversations.')
    } finally {
      setLoadingConvs(false)
    }
  }, [user?.id])

  useEffect(() => { loadConversations() }, [loadConversations])

  // ── Handle URL param — open conversation from History ─────────
  useEffect(() => {
    if (urlConvId && urlConvId !== selectedConvId) {
      setSelectedConvId(urlConvId)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlConvId])

  // ── Load messages when selected conversation changes ─────────
  useEffect(() => {
    if (!selectedConvId || !user?.id) {
      setMessages([])
      return
    }
    if (skipFetchConvIdRef.current === selectedConvId) {
      skipFetchConvIdRef.current = null
      return
    }
    setLoadingMsgs(true)
    setError(null)
    fetchMessages(selectedConvId, user.id)
      .then((data) => {
        setMessages((data.messages || []).map(normaliseMessage))
      })
      .catch((err) => {
        setError(err.message || 'Failed to load messages.')
        setMessages([])
      })
      .finally(() => setLoadingMsgs(false))
  }, [selectedConvId, user?.id])

  // ── Select a conversation (also updates the URL) ─────────────
  const selectConversation = useCallback((convId) => {
    setSelectedConvId(convId)
    navigate(`/chat/${convId}`, { replace: true })
  }, [navigate])

  // ── Delete a conversation (Interactive Modal) ────────────────
  const handleDeleteClick = (conv, e) => {
    e.stopPropagation()
    setConvToDelete(conv)
  }

  const confirmDeleteConversation = useCallback(async () => {
    if (!convToDelete || !user?.id) return
    const convId = convToDelete.id
    setIsDeletingConv(true)
    try {
      await deleteConversation(convId, user.id)
      setConversations((prev) => prev.filter((c) => c.id !== convId))
      if (selectedConvId === convId) {
        setSelectedConvId(null)
        setMessages([])
        navigate('/chat', { replace: true })
      }
      setConvToDelete(null)
    } catch (err) {
      setError(err.message || 'Failed to delete conversation.')
    } finally {
      setIsDeletingConv(false)
    }
  }, [convToDelete, user?.id, selectedConvId, navigate])

  // ── Load available indexed documents ─────────────────────────
  useEffect(() => {
    if (!user?.id) return
    setLoadingAvailableDocs(true)
    fetch(`${API_BASE_URL}/api/documents?user_id=${user.id}&scope=both&status=Indexed&page_size=100`)
      .then((r) => r.json())
      .then((data) => {
        setAvailableDocs(data.documents || [])
        setLoadingAvailableDocs(false)
      })
      .catch(() => setLoadingAvailableDocs(false))
  }, [user?.id])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const toggleDocId = (id) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    )
  }

  const handleFileAttach = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setError(null)
    setParsingFile(true)
    try {
      const parsed = await parseChatFile(file)
      setAttachments((prev) => [
        ...prev,
        {
          filename:   parsed.filename,
          file_type:  parsed.file_type,
          text:       parsed.text,
          char_count: parsed.char_count,
          page_count: parsed.page_count,
        },
      ])
    } catch (err) {
      setError(`Failed to process attachment: ${err.message}`)
    } finally {
      setParsingFile(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const removeAttachment = (index) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  const sendMessage = useCallback(async () => {
    if ((!input.trim() && attachments.length === 0) || isTyping) return
    setError(null)

    const currentAtts = [...attachments]
    const userText = input.trim() || (attachments.length > 0 ? `[Attached file: ${attachments.map(a => a.filename).join(', ')}]` : '')

    // Optimistic UI: show user message immediately
    const optimisticUserMsg = {
      id:          `opt-${Date.now()}`,
      role:        'user',
      content:     userText,
      timestamp:   new Date().toISOString(),
      attachments: currentAtts,
      citations:   [],
      ragEnabled:  false,
    }

    const history = messages.filter((m) => !m.isError)
    setMessages((prev) => [...prev, optimisticUserMsg])
    setInput('')
    setAttachments([])
    setIsTyping(true)

    // ── Ensure a real backend conversation exists ─────────────
    let convId = selectedConvId
    let isNewConv = false
    const existingConv = conversations.find((c) => c.id === convId)
    const isGenericTitle = !existingConv || ['new conversation', 'new chat', 'greeting exchange', 'hi', 'hello', 'hey', 'untitled'].includes((existingConv.title || '').trim().toLowerCase())

    if (!convId) {
      try {
        const cleanTxt = userText.trim()
        const normFirst = cleanTxt.toLowerCase().replace(/[!?.,]/g, '')
        const isGreeting = ['hi', 'hello', 'hey', 'heya', 'howdy', 'good morning', 'good afternoon', 'good evening', 'thanks', 'thank you', 'sup', 'yo'].includes(normFirst)
        const initialTitle = isGreeting
          ? 'Greeting Exchange'
          : (cleanTxt.length > 50 ? cleanTxt.slice(0, 50) + '…' : (cleanTxt.charAt(0).toUpperCase() + cleanTxt.slice(1)))

        const result = await createConversation(user.id, initialTitle)
        convId = result.conversation.id
        isNewConv = true
        skipFetchConvIdRef.current = convId
        setConversations((prev) => [result.conversation, ...prev])
        setSelectedConvId(convId)
        navigate(`/chat/${convId}`, { replace: true })
      } catch (err) {
        setIsTyping(false)
        setError(err.message || 'Failed to create conversation.')
        setMessages((prev) => prev.filter((m) => m.id !== optimisticUserMsg.id))
        setInput(userText)
        setAttachments(currentAtts)
        return
      }
    }

    try {
      let aiMsg

      if (ragEnabled) {
        // /api/rag/chat auto-persists both messages in the backend
        const data = await sendRAGMessage(userText, {
          document_ids: selectedDocIds.length > 0 ? selectedDocIds : null,
          conversation_history: history.map((m) => ({
            role:    m.role === 'assistant' ? 'model' : m.role,
            content: m.content,
          })),
          attachments: currentAtts.length > 0 ? currentAtts : null,
        })
        aiMsg = {
          id:             `ai-${Date.now()}`,
          role:           'assistant',
          content:        data.answer,
          timestamp:      data.timestamp || new Date().toISOString(),
          model:          data.model,
          processingTime: data.processing_time?.toFixed(2),
          ragEnabled:     true,
          citations:      data.citations || [],
          usedFallback:   data.used_fallback || false,
          attachments:    [],
        }
      } else {
        const data = await sendChatMessage(userText, history, {
          attachments: currentAtts.length > 0 ? currentAtts : null,
        })
        aiMsg = {
          id:             `ai-${Date.now()}`,
          role:           'assistant',
          content:        data.response,
          timestamp:      data.timestamp || new Date().toISOString(),
          model:          data.model,
          processingTime: data.processing_time?.toFixed(2),
          ragEnabled:     false,
          citations:      [],
          usedFallback:   false,
          attachments:    [],
        }
      }

      setIsTyping(false)
      setMessages((prev) => [...prev, aiMsg])

      // Persist messages in database (non-blocking for UI)
      if (user?.id && convId) {
        appendMessage(convId, user.id, 'user', userText).catch((err) =>
          console.warn('Failed to persist user message:', err)
        )
        appendMessage(convId, user.id, 'assistant', aiMsg.content, aiMsg.citations).catch((err) =>
          console.warn('Failed to persist assistant message:', err)
        )

        // Dynamically name or re-name the chat with LLM if title is generic
        const normMsg = userText.trim().toLowerCase().replace(/[!?.,]/g, '')
        const isNotJustGreeting = !['hi', 'hello', 'hey', 'heya', 'howdy', 'good morning', 'good afternoon', 'good evening', 'thanks', 'thank you'].includes(normMsg) && userText.trim().length > 3

        if ((isNewConv || isGenericTitle) && isNotJustGreeting) {
          generateConversationTitle(convId, user.id, userText)
            .then((res) => {
              if (res?.title) {
                setConversations((prev) =>
                  prev.map((c) => (c.id === convId ? { ...c, title: res.title } : c))
                )
              }
            })
            .catch((err) => console.warn('Dynamic title generation skipped:', err))
        }
      }

      // Update sidebar preview + bump updated_at locally
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? { ...c, updated_at: new Date().toISOString() }
            : c
        )
      )
    } catch (err) {
      setIsTyping(false)
      setError(err.message || 'An unexpected error occurred.')
      // Roll back optimistic user message
      setMessages((prev) => prev.filter((m) => m.id !== optimisticUserMsg.id))
      setInput(userText)
      setAttachments(currentAtts)
    }
  }, [input, attachments, isTyping, messages, selectedConvId, ragEnabled, selectedDocIds, user?.id, navigate])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const startNewChat = () => {
    setMessages([])
    setSelectedConvId(null)
    setInput('')
    setError(null)
    skipFetchConvIdRef.current = null
    navigate('/chat', { replace: true })
    setTimeout(() => inputRef.current?.focus(), 100)
  }

  const SUGGESTIONS = [
    'Summarize the uploaded documents',
    'What is the leave policy?',
    'List key security requirements',
    'Explain the onboarding process',
  ]

  return (
    <div className="flex h-[calc(100vh-64px)] bg-surface-50">
      {/* ── Sidebar ── */}
      <div className="w-72 flex-shrink-0 bg-surface-50 border-r border-surface-200 flex flex-col">
        <div className="p-4 border-b border-surface-100 space-y-3">
          <div className="flex gap-2">
            <Button className="flex-1" onClick={startNewChat}>
              <Plus size={16} /> New Chat
            </Button>
            <button
              onClick={loadConversations}
              disabled={loadingConvs}
              title="Refresh conversations"
              className="px-2.5 rounded-lg border border-surface-200 text-surface-400 hover:text-surface-700 hover:bg-surface-100 transition-colors disabled:opacity-50"
            >
              <RefreshCw size={13} className={loadingConvs ? 'animate-spin' : ''} />
            </button>
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search chats..."
              className="w-full pl-8 pr-3 py-2 text-xs bg-surface-100 border border-transparent rounded-lg outline-none focus:bg-surface-50 focus:border-primary-500/40 text-surface-700 placeholder:text-surface-400 transition-all"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {/* Loading skeleton */}
          {loadingConvs && conversations.length === 0 && (
            <div className="px-3 py-6 space-y-2">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="animate-pulse space-y-1.5">
                  <div className="h-3 bg-surface-200 rounded w-4/5" />
                  <div className="h-2.5 bg-surface-100 rounded w-3/5" />
                </div>
              ))}
            </div>
          )}

          {/* Conversation load error */}
          {convError && !loadingConvs && (
            <div className="px-3 py-4 text-center">
              <AlertCircle size={18} className="text-red-400 mx-auto mb-1" />
              <p className="text-[11px] text-red-400">{convError}</p>
              <button onClick={loadConversations} className="mt-2 text-[11px] text-primary-400 underline">Retry</button>
            </div>
          )}

          {/* Empty state */}
          {!loadingConvs && !convError && filteredConvs.length === 0 && (
            <div className="px-3 py-8 text-center">
              <MessageSquare size={24} className="text-surface-400 mx-auto mb-2" />
              <p className="text-xs text-surface-500">
                {searchQuery ? 'No matching conversations' : 'No conversations yet'}
              </p>
              <p className="text-[11px] text-surface-400 mt-1">Start a new chat above</p>
            </div>
          )}

          {/* Conversation list */}
          {!convError && filteredConvs.map((conv) => (
            <div key={conv.id} className="group relative">
              <button
                onClick={() => selectConversation(conv.id)}
                className={`w-full text-left px-3 py-2.5 rounded-xl transition-all duration-150 pr-8 ${
                  selectedConvId === conv.id
                    ? 'bg-primary-600/10 border border-primary-500/30'
                    : 'hover:bg-surface-100 border border-transparent'
                }`}
              >
                <div className="flex items-start gap-2">
                  <MessageSquare size={13} className={`mt-0.5 flex-shrink-0 ${selectedConvId === conv.id ? 'text-primary-400' : 'text-surface-400'}`} />
                  <div className="flex-1 min-w-0">
                    <p className={`text-xs font-medium truncate ${selectedConvId === conv.id ? 'text-primary-300' : 'text-surface-700'}`}>
                      {conv.title || 'New Conversation'}
                    </p>
                    <div className="flex items-center gap-1 mt-1">
                      <Clock size={9} className="text-surface-400" />
                      <span className="text-[10px] text-surface-500">
                        {new Date(conv.updated_at || conv.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </span>
                    </div>
                  </div>
                </div>
              </button>
              {/* Delete button — visible on hover */}
              <button
                onClick={(e) => handleDeleteClick(conv, e)}
                title="Delete conversation"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded-lg text-surface-400 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ── Main chat area ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="h-14 px-5 flex items-center justify-between border-b border-surface-200 bg-surface-50 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary-600/15 flex items-center justify-center">
              <Bot size={15} className="text-primary-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-surface-900">{selectedConv?.title || 'New Conversation'}</p>
              <p className="text-xs text-surface-500 flex items-center gap-1">
                <Zap size={10} className="text-emerald-400" />
                Enterprise AI · {messages.length} messages
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <RAGToggle enabled={ragEnabled} onToggle={() => setRagEnabled((r) => !r)} />
            {ragEnabled && (
              <button
                onClick={() => setIsDocPanelOpen((o) => !o)}
                title="Select specific knowledge base documents"
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                  selectedDocIds.length > 0 || isDocPanelOpen
                    ? 'bg-primary-600/20 border-primary-500/40 text-primary-300'
                    : 'bg-surface-100 border-surface-200 text-surface-600 hover:border-surface-300'
                }`}
              >
                <BookOpen size={13} className="text-primary-400" />
                <span>
                  {selectedDocIds.length > 0
                    ? `${selectedDocIds.length} doc${selectedDocIds.length > 1 ? 's' : ''} selected`
                    : 'Select Documents'}
                </span>
                {isDocPanelOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
            )}
          </div>
        </div>

        {/* Document Knowledge Base Selector Panel */}
        <AnimatePresence>
          {ragEnabled && isDocPanelOpen && (
            <ChatDocumentSelectorPanel
              selectedIds={selectedDocIds}
              onToggle={toggleDocId}
              onSelectAll={(ids) => setSelectedDocIds(ids)}
              onClear={() => setSelectedDocIds([])}
              onClose={() => setIsDocPanelOpen(false)}
              allDocs={availableDocs}
              loadingDocs={loadingAvailableDocs}
            />
          )}
        </AnimatePresence>

        {/* Error banner */}
        <AnimatePresence>
          {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        </AnimatePresence>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {/* Loading messages spinner */}
          {loadingMsgs && (
            <div className="h-full flex items-center justify-center">
              <div className="flex flex-col items-center gap-3">
                <Loader2 size={28} className="animate-spin text-primary-400" />
                <p className="text-xs text-surface-500">Loading messages…</p>
              </div>
            </div>
          )}

          {/* Empty / welcome state */}
          {!loadingMsgs && messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary-600/15 flex items-center justify-center mb-4">
                <Bot size={28} className="text-primary-400" />
              </div>
              <h3 className="text-lg font-semibold text-surface-900">
                {selectedConvId ? 'No messages yet' : 'Start a conversation'}
              </h3>
              <p className="text-sm text-surface-500 mt-1.5 max-w-xs">
                {ragEnabled
                  ? selectedDocIds.length > 0
                    ? `Searching ${selectedDocIds.length} selected document${selectedDocIds.length > 1 ? 's' : ''}`
                    : 'Answers grounded in all your uploaded documents with citations'
                  : 'Asking AI directly — toggle Docs ON to use your knowledge base'}
              </p>
              {ragEnabled && (
                <div className="flex items-center gap-1.5 mt-3 text-xs text-primary-400 bg-primary-600/10 border border-primary-500/20 rounded-lg px-3 py-1.5">
                  <Database size={12} />
                  {selectedDocIds.length > 0 ? `${selectedDocIds.length} document filter active` : 'Document knowledge base active'}
                </div>
              )}
              {!selectedConvId && (
                <div className="flex flex-wrap gap-2 mt-5 justify-center max-w-md">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => { setInput(s); inputRef.current?.focus() }}
                      className="px-3 py-1.5 bg-surface-100 border border-surface-200 rounded-lg text-xs text-surface-600 hover:bg-primary-600/10 hover:border-primary-500/30 hover:text-primary-300 transition-all"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Message list */}
          {!loadingMsgs && messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              msg={msg}
              userName={getUserDisplayName()}
              userAvatar={getUserAvatar()}
              onCitationClick={(c) => setSelectedCitation({ ...c, aiAnswer: msg.content })}
            />
          ))}

          {isTyping && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>

        {/* Hidden file input for paperclip button */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileAttach}
          accept=".pdf,.docx,.txt,.csv,.md,.json,.py,.js,.ts,.log,.html,.yml,.yaml"
          className="hidden"
        />

        {/* Input area */}
        <div className="p-4 bg-surface-50 border-t border-surface-200">
          {ragEnabled && (
            <div className="flex items-center gap-2 mb-2.5 flex-wrap text-[11px]">
              <span className="font-semibold text-primary-400 flex items-center gap-1">
                <Database size={11} />
                Active Knowledge Context:
              </span>
              {selectedDocIds.length === 0 ? (
                <span className="text-surface-500 bg-surface-200/80 px-2.5 py-0.5 rounded-md font-medium">
                  All Indexed Documents (Company + Workspace)
                </span>
              ) : (
                <div className="flex items-center gap-1.5 flex-wrap">
                  {availableDocs
                    .filter((d) => selectedDocIds.includes(d.id))
                    .map((doc) => (
                      <span
                        key={doc.id}
                        className="inline-flex items-center gap-1.5 bg-primary-600/15 border border-primary-500/30 text-primary-300 rounded-lg px-2.5 py-0.5 font-medium shadow-sm"
                      >
                        <FileText size={10} className="text-primary-400" />
                        <span className="truncate max-w-[150px]">{doc.file_name}</span>
                        <button
                          onClick={() => toggleDocId(doc.id)}
                          className="text-primary-400 hover:text-red-400 transition-colors ml-0.5"
                        >
                          <X size={11} />
                        </button>
                      </span>
                    ))}
                  <button
                    onClick={() => setSelectedDocIds([])}
                    className="text-[10px] text-surface-400 hover:text-surface-200 underline ml-1 font-medium"
                  >
                    Clear Selection
                  </button>
                </div>
              )}
            </div>
          )}
          <div className="bg-surface-100 rounded-2xl px-4 py-3 border border-surface-200 focus-within:border-primary-500/50 focus-within:ring-2 focus-within:ring-primary-500/10 transition-all">
            {/* Attachment chips */}
            {attachments.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pb-2 mb-2 border-b border-surface-200/60">
                {attachments.map((att, idx) => (
                  <div key={idx} className="flex items-center gap-1.5 bg-primary-600/15 border border-primary-500/30 rounded-lg px-2.5 py-1 text-xs text-primary-300">
                    <FileText size={12} className="text-primary-400" />
                    <span className="font-medium truncate max-w-[160px]">{att.filename}</span>
                    <span className="text-[10px] text-surface-400">({(att.char_count / 1000).toFixed(1)}k chars)</span>
                    <button
                      type="button"
                      onClick={() => removeAttachment(idx)}
                      className="text-surface-400 hover:text-red-400 transition-colors ml-1"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-end gap-3">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={parsingFile || isTyping}
                title="Attach document (PDF, DOCX, TXT, CSV, MD)"
                className="text-surface-400 hover:text-primary-400 transition-colors flex-shrink-0 mb-0.5 disabled:opacity-50"
              >
                {parsingFile ? <Loader2 size={18} className="animate-spin text-primary-400" /> : <Paperclip size={18} />}
              </button>
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={attachments.length > 0 ? "Ask a question about the attached file..." : "Ask anything about your documents…"}
                rows={1}
                disabled={isTyping}
                className="flex-1 bg-transparent text-sm text-surface-800 outline-none resize-none placeholder:text-surface-400 max-h-32 disabled:opacity-60"
                style={{ lineHeight: '1.5' }}
              />
              <Button
                onClick={sendMessage}
                disabled={(!input.trim() && attachments.length === 0) || isTyping || parsingFile}
                size="sm"
                className="!rounded-xl flex-shrink-0"
              >
                <Send size={15} />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Interactive Delete Confirmation Modal ── */}
      <Modal
        isOpen={Boolean(convToDelete)}
        onClose={() => !isDeletingConv && setConvToDelete(null)}
        title="Delete Conversation"
        size="sm"
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center flex-shrink-0 text-red-500">
              <Trash2 size={18} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-surface-800 font-semibold">
                Are you sure you want to delete this chat?
              </p>
              <p className="text-xs text-surface-500 mt-1 bg-surface-50 p-2 rounded-lg border border-surface-200/60 truncate font-mono">
                "{convToDelete?.title || 'New Conversation'}"
              </p>
              <p className="text-xs text-red-500/90 mt-2">
                This action cannot be undone. All messages will be permanently removed.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-surface-200/60">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setConvToDelete(null)}
              disabled={isDeletingConv}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={confirmDeleteConversation}
              loading={isDeletingConv}
            >
              Delete
            </Button>
          </div>
        </div>
      </Modal>

      {/* Interactive PDF Citation Highlight Viewer Modal */}
      <PDFCitationViewerModal
        citation={selectedCitation}
        userId={user?.id}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  )
}
