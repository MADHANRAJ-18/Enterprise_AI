import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, Plus, Bot, Paperclip, MessageSquare, Clock,
  Search, AlertCircle, Zap, BookOpen, ChevronDown,
  ChevronUp, Database, ToggleLeft, ToggleRight,
  X, CheckCircle, Info, Filter, FileText, Loader2
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { Avatar } from '../../components/ui/Avatar'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { sendRAGMessage, sendChatMessage, parseChatFile } from '../../services/chatService'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

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
function CitationsPanel({ citations, usedFallback }) {
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
                  className="flex items-start gap-2 bg-surface-200 border border-surface-300 rounded-lg px-3 py-2"
                >
                  <span className="text-[10px] font-bold text-primary-400 bg-primary-400/10 border border-primary-400/20 rounded px-1.5 py-0.5 flex-shrink-0 mt-0.5">
                    [{c.source_index}]
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs font-medium text-surface-800 truncate">{c.file_name}</span>
                      {c.page_number && (
                        <span className="text-[10px] text-surface-500">p.{c.page_number}</span>
                      )}
                    </div>
                    <p className="text-[11px] text-surface-500 mt-0.5 line-clamp-2">
                      {c.text_preview}
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
function MessageBubble({ msg, userName, userAvatar }) {
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
            <CitationsPanel citations={msg.citations} usedFallback={msg.usedFallback} />
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ── Document filter picker ────────────────────────────────────
function DocumentFilter({ selectedIds, onToggle, onClear }) {
  const { user } = useAuth()
  const [docs, setDocs] = useState([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!user?.id) return
    fetch(`${API_BASE_URL}/api/documents?user_id=${user.id}&status=Indexed&page_size=50`)
      .then((r) => r.json())
      .then((data) => setDocs(data.documents || []))
      .catch(() => {})
  }, [user?.id])

  const count = selectedIds.length

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        title="Filter by specific documents"
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all ${
          count > 0
            ? 'bg-primary-600/20 border-primary-500/40 text-primary-300'
            : 'bg-surface-100 border-surface-200 text-surface-500 hover:border-surface-300'
        }`}
      >
        <Filter size={12} />
        {count > 0 ? `${count} doc${count > 1 ? 's' : ''}` : 'All docs'}
        {open ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            className="absolute right-0 top-9 z-50 w-72 bg-surface-100 border border-surface-200 rounded-xl shadow-xl overflow-hidden"
          >
            <div className="px-3 py-2 border-b border-surface-200 flex items-center justify-between">
              <span className="text-xs font-semibold text-surface-700">Filter by document</span>
              {count > 0 && (
                <button onClick={() => { onClear(); }} className="text-[11px] text-primary-400 hover:text-primary-300">
                  Clear all
                </button>
              )}
            </div>
            <div className="max-h-60 overflow-y-auto p-1.5 space-y-0.5">
              {docs.length === 0 ? (
                <p className="text-xs text-surface-500 text-center py-4">No processed documents yet</p>
              ) : docs.map((doc) => {
                const sel = selectedIds.includes(doc.id)
                return (
                  <button
                    key={doc.id}
                    onClick={() => onToggle(doc.id)}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all ${
                      sel
                        ? 'bg-primary-600/15 border border-primary-500/30'
                        : 'hover:bg-surface-200 border border-transparent'
                    }`}
                  >
                    <FileText size={13} className={sel ? 'text-primary-400' : 'text-surface-500'} />
                    <span className={`text-xs truncate flex-1 ${sel ? 'text-primary-300 font-medium' : 'text-surface-700'}`}>
                      {doc.file_name}
                    </span>
                    {sel && <CheckCircle size={12} className="text-primary-400 flex-shrink-0" />}
                  </button>
                )
              })}
            </div>
            <div className="px-3 py-2 border-t border-surface-200">
              <p className="text-[11px] text-surface-500">
                {count === 0 ? 'Searching all documents' : `Searching ${count} selected document${count > 1 ? 's' : ''}`}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
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
  const { getUserDisplayName, getUserAvatar } = useAuth()
  const [conversations, setConversations] = useState([])
  const [selectedConvId, setSelectedConvId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [error, setError] = useState(null)
  const [ragEnabled, setRagEnabled] = useState(true)
  const [selectedDocIds, setSelectedDocIds] = useState([])   // [] = all docs
  const [attachments, setAttachments] = useState([])         // direct file attachments
  const [parsingFile, setParsingFile] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)

  const selectedConv = conversations.find((c) => c.id === selectedConvId) || null
  const filteredConvs = conversations.filter(
    (c) => c.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

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
    const userMsg = {
      id:          `m${Date.now()}`,
      role:        'user',
      content:     userText,
      timestamp:   new Date().toISOString(),
      attachments: currentAtts,
    }

    const history = messages.filter((m) => !m.isError)
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setAttachments([])
    setIsTyping(true)

    let convId = selectedConvId
    if (!convId) {
      convId = `conv-${Date.now()}`
      const title = userText.length > 45 ? userText.slice(0, 45) + '…' : userText
      setConversations((prev) => [
        { id: convId, title, preview: userText, createdAt: new Date().toISOString(), messageCount: 0 },
        ...prev,
      ])
      setSelectedConvId(convId)
    }

    try {
      let aiMsg

      if (ragEnabled) {
        const data = await sendRAGMessage(userText, {
          document_ids: selectedDocIds.length > 0 ? selectedDocIds : null,
          conversation_history: history.map((m) => ({
            role:    m.role === 'assistant' ? 'model' : m.role,
            content: m.content,
          })),
          attachments: currentAtts.length > 0 ? currentAtts : null,
        })
        aiMsg = {
          id:             `m${Date.now() + 1}`,
          role:           'assistant',
          content:        data.answer,
          timestamp:      data.timestamp || new Date().toISOString(),
          model:          data.model,
          processingTime: data.processing_time?.toFixed(2),
          ragEnabled:     true,
          citations:      data.citations || [],
          usedFallback:   data.used_fallback || false,
        }
      } else {
        const data = await sendChatMessage(userText, history, {
          attachments: currentAtts.length > 0 ? currentAtts : null,
        })
        aiMsg = {
          id:             `m${Date.now() + 1}`,
          role:           'assistant',
          content:        data.response,
          timestamp:      data.timestamp || new Date().toISOString(),
          model:          data.model,
          processingTime: data.processing_time?.toFixed(2),
          ragEnabled:     false,
          citations:      [],
          usedFallback:   false,
        }
      }

      setIsTyping(false)
      setMessages((prev) => [...prev, aiMsg])
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? { ...c, messageCount: (c.messageCount || 0) + 2, preview: userText }
            : c
        )
      )
    } catch (err) {
      setIsTyping(false)
      setError(err.message || 'An unexpected error occurred.')
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id))
      setInput(userText)
      setAttachments(currentAtts)
    }
  }, [input, attachments, isTyping, messages, selectedConvId, ragEnabled, selectedDocIds])

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
          <Button className="w-full" onClick={startNewChat}>
            <Plus size={16} /> New Chat
          </Button>
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
          {filteredConvs.length === 0 ? (
            <div className="px-3 py-8 text-center">
              <MessageSquare size={24} className="text-surface-400 mx-auto mb-2" />
              <p className="text-xs text-surface-500">No conversations yet</p>
              <p className="text-[11px] text-surface-400 mt-1">Start a new chat above</p>
            </div>
          ) : (
            filteredConvs.map((conv) => (
              <button
                key={conv.id}
                onClick={() => setSelectedConvId(conv.id)}
                className={`w-full text-left px-3 py-2.5 rounded-xl transition-all duration-150 ${
                  selectedConvId === conv.id
                    ? 'bg-primary-600/10 border border-primary-500/30'
                    : 'hover:bg-surface-100 border border-transparent'
                }`}
              >
                <div className="flex items-start gap-2">
                  <MessageSquare size={13} className={`mt-0.5 flex-shrink-0 ${selectedConvId === conv.id ? 'text-primary-400' : 'text-surface-400'}`} />
                  <div className="flex-1 min-w-0">
                    <p className={`text-xs font-medium truncate ${selectedConvId === conv.id ? 'text-primary-300' : 'text-surface-700'}`}>
                      {conv.title}
                    </p>
                    <p className="text-[11px] text-surface-500 truncate mt-0.5">{conv.preview}</p>
                    <div className="flex items-center gap-1 mt-1">
                      <Clock size={9} className="text-surface-400" />
                      <span className="text-[10px] text-surface-500">
                        {new Date(conv.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </span>
                    </div>
                  </div>
                </div>
              </button>
            ))
          )}
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
              <DocumentFilter
                selectedIds={selectedDocIds}
                onToggle={toggleDocId}
                onClear={() => setSelectedDocIds([])}
              />
            )}
          </div>
        </div>

        {/* Error banner */}
        <AnimatePresence>
          {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        </AnimatePresence>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary-600/15 flex items-center justify-center mb-4">
                <Bot size={28} className="text-primary-400" />
              </div>
              <h3 className="text-lg font-semibold text-surface-900">Start a conversation</h3>
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
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              msg={msg}
              userName={getUserDisplayName()}
              userAvatar={getUserAvatar()}
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
            <div className="flex items-center gap-1.5 mb-2 text-[11px] text-surface-500">
              <CheckCircle size={10} className="text-primary-400" />
              {selectedDocIds.length > 0
                ? `Searching ${selectedDocIds.length} selected document${selectedDocIds.length > 1 ? 's' : ''} · citations included`
                : 'Searching all documents · citations included'
              }
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
          <p className="text-center text-[11px] text-surface-500 mt-2">
            Powered by Enterprise AI · Verify critical information independently.
          </p>
        </div>
      </div>
    </div>
  )
}
