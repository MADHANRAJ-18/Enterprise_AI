import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Search, Filter, MessageSquare, Clock, ChevronDown,
  ChevronUp, Download, Calendar, Bot, Tag, Loader2,
  AlertCircle, Trash2, ExternalLink
} from 'lucide-react'
import { Card, CardHeader, CardBody } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'
import { useAuth } from '../../context/AuthContext'
import {
  fetchConversations,
  fetchMessages,
  deleteConversation,
} from '../../services/chatService'

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

// ── Expandable conversation row ───────────────────────────────
function ConversationRow({ conv, userId, onDeleteRequest }) {
  const [expanded, setExpanded]     = useState(false)
  const [messages, setMessages]     = useState([])
  const [loadingMsgs, setLoadingMsgs] = useState(false)
  const navigate = useNavigate()

  const handleExpand = useCallback(async () => {
    const willExpand = !expanded
    setExpanded(willExpand)
    if (willExpand && messages.length === 0) {
      setLoadingMsgs(true)
      try {
        const data = await fetchMessages(conv.id, userId)
        setMessages(data.messages || [])
      } catch (_) {
        // silently ignore preview fetch error — messages stay empty
      } finally {
        setLoadingMsgs(false)
      }
    }
  }, [expanded, messages.length, conv.id, userId])

  const handleDelete = (e) => {
    e.stopPropagation()
    onDeleteRequest(conv)
  }

  const messageCount = messages.length

  return (
    <motion.div layout className="border-b border-surface-100 last:border-0">
      <button
        className="w-full text-left px-5 py-4 hover:bg-surface-50 transition-colors group"
        onClick={handleExpand}
      >
        <div className="flex items-start gap-4">
          <div className="w-9 h-9 rounded-xl bg-primary-50 flex items-center justify-center flex-shrink-0 mt-0.5">
            <MessageSquare size={16} className="text-primary-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-surface-900 group-hover:text-primary-600 transition-colors truncate">
                {conv.title || 'Untitled Conversation'}
              </p>
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* Open in Chat */}
                <button
                  onClick={(e) => { e.stopPropagation(); navigate(`/chat/${conv.id}`) }}
                  title="Open in Chat"
                  className="p-1 rounded-lg text-surface-400 hover:text-primary-400 hover:bg-primary-500/10 opacity-0 group-hover:opacity-100 transition-all"
                >
                  <ExternalLink size={12} />
                </button>
                {/* Delete */}
                <button
                  onClick={handleDelete}
                  title="Delete conversation"
                  className="p-1 rounded-lg text-surface-400 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                >
                  <Trash2 size={12} />
                </button>
                <div className="flex items-center gap-1 text-xs text-surface-400">
                  <Clock size={11} />
                  {formatDate(conv.updated_at || conv.created_at)}
                </div>
                {expanded ? (
                  <ChevronUp size={15} className="text-surface-400" />
                ) : (
                  <ChevronDown size={15} className="text-surface-400" />
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <div className="flex items-center gap-1">
                <Bot size={11} className="text-surface-400" />
                <Badge variant="gray">Enterprise AI</Badge>
              </div>
              {messageCount > 0 && (
                <span className="text-xs text-surface-400">{messageCount} messages</span>
              )}
            </div>
          </div>
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-4 pt-1 bg-surface-50 space-y-2">
              <p className="text-xs font-semibold text-surface-400 uppercase tracking-wide mb-3">
                Conversation Preview
              </p>

              {loadingMsgs && (
                <div className="flex items-center gap-2 py-4 text-xs text-surface-400">
                  <Loader2 size={14} className="animate-spin text-primary-400" />
                  Loading messages…
                </div>
              )}

              {!loadingMsgs && messages.length > 0 &&
                messages.slice(0, 3).map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                  >
                    <div className={`rounded-xl px-3 py-2 text-xs max-w-[75%] leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-primary-600 text-white'
                        : 'bg-surface-100 border border-surface-200 text-surface-700'
                    }`}>
                      <p className="line-clamp-2">
                        {(msg.content || '').substring(0, 120)}
                        {(msg.content || '').length > 120 ? '…' : ''}
                      </p>
                    </div>
                  </div>
                ))
              }

              {!loadingMsgs && messages.length === 0 && (
                <p className="text-xs text-surface-400 italic">No messages in this conversation.</p>
              )}

              {/* Open full conversation */}
              {messages.length > 0 && (
                <button
                  onClick={() => navigate(`/chat/${conv.id}`)}
                  className="mt-2 text-xs text-primary-400 hover:text-primary-300 flex items-center gap-1.5 transition-colors"
                >
                  <ExternalLink size={11} /> Open full conversation
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ── Main HistoryPage ──────────────────────────────────────────
export function HistoryPage() {
  const { user } = useAuth()
  const [conversations, setConversations] = useState([])
  const [loading, setLoading]             = useState(false)
  const [error, setError]                 = useState(null)
  const [search, setSearch]               = useState('')
  const [sortOrder, setSortOrder]         = useState('newest')
  const [convToDelete, setConvToDelete]   = useState(null)
  const [isDeleting, setIsDeleting]       = useState(false)

  const loadConversations = useCallback(async () => {
    if (!user?.id) return
    setLoading(true)
    setError(null)
    try {
      const data = await fetchConversations(user.id)
      setConversations(data.conversations || [])
    } catch (err) {
      setError(err.message || 'Failed to load conversation history.')
    } finally {
      setLoading(false)
    }
  }, [user?.id])

  useEffect(() => { loadConversations() }, [loadConversations])

  const confirmDelete = async () => {
    if (!convToDelete || !user?.id) return
    const convId = convToDelete.id
    setIsDeleting(true)
    try {
      await deleteConversation(convId, user.id)
      setConversations((prev) => prev.filter((c) => c.id !== convId))
      setConvToDelete(null)
    } catch (err) {
      alert(`Failed to delete: ${err.message}`)
    } finally {
      setIsDeleting(false)
    }
  }

  const filtered = conversations
    .filter((c) => {
      const title = (c.title || '').toLowerCase()
      return title.includes(search.toLowerCase())
    })
    .sort((a, b) => {
      const dateA = new Date(a.updated_at || a.created_at)
      const dateB = new Date(b.updated_at || b.created_at)
      if (sortOrder === 'newest') return dateB - dateA
      if (sortOrder === 'oldest') return dateA - dateB
      return 0
    })

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="p-6 max-w-5xl mx-auto space-y-6"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Conversation History</h1>
          <p className="text-sm text-surface-500 mt-0.5">
            {loading ? 'Loading…' : `${conversations.length} total conversation${conversations.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={loadConversations} disabled={loading}>
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          {loading ? 'Loading…' : 'Refresh'}
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold text-surface-900">
            {loading ? '—' : conversations.length}
          </p>
          <p className="text-xs text-surface-500 font-medium mt-0.5">Total Conversations</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold text-surface-900">
            {loading ? '—' : '—'}
          </p>
          <p className="text-xs text-surface-500 font-medium mt-0.5">Total Messages</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold text-surface-900">1</p>
          <p className="text-xs text-surface-500 font-medium mt-0.5">Agents Active</p>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3 flex-wrap">
            {/* Search */}
            <div className="relative flex-1 min-w-48">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search conversations..."
                className="w-full pl-8 pr-3 py-2 text-sm bg-surface-100 border border-transparent rounded-lg outline-none focus:bg-surface-50 focus:border-primary-300 transition-all"
              />
            </div>

            {/* Sort */}
            <div className="relative">
              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                className="pl-3 pr-8 py-2 text-sm bg-surface-100 border border-transparent rounded-lg outline-none focus:bg-surface-50 focus:border-primary-300 transition-all appearance-none cursor-pointer"
              >
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
              </select>
              <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-400 pointer-events-none" />
            </div>
          </div>
        </CardHeader>

        <div>
          {/* Loading state */}
          {loading && (
            <div className="py-16 text-center">
              <Loader2 size={28} className="animate-spin text-primary-400 mx-auto mb-3" />
              <p className="text-sm text-surface-500">Loading conversation history…</p>
            </div>
          )}

          {/* Error state */}
          {!loading && error && (
            <div className="py-16 text-center">
              <AlertCircle size={28} className="text-red-400 mx-auto mb-3" />
              <p className="text-sm font-medium text-surface-700">Failed to load history</p>
              <p className="text-xs text-surface-400 mt-1">{error}</p>
              <button
                onClick={loadConversations}
                className="mt-4 text-sm text-primary-400 underline hover:text-primary-300"
              >
                Try again
              </button>
            </div>
          )}

          {/* Conversation rows */}
          {!loading && !error && (
            filtered.length > 0 ? (
              filtered.map((conv) => (
                <ConversationRow
                  key={conv.id}
                  conv={conv}
                  userId={user?.id}
                  onDeleteRequest={(c) => setConvToDelete(c)}
                />
              ))
            ) : (
              <div className="py-16 text-center">
                <MessageSquare size={32} className="text-surface-300 mx-auto mb-3" />
                <p className="text-sm font-medium text-surface-500">
                  {search ? 'No conversations match your search' : 'No conversations yet'}
                </p>
                <p className="text-xs text-surface-400 mt-1">
                  {search ? 'Try adjusting your search' : 'Start a new chat to see it here'}
                </p>
              </div>
            )
          )}
        </div>

        {!loading && !error && filtered.length > 0 && (
          <div className="px-5 py-3 border-t border-surface-100 bg-surface-50/50 rounded-b-xl">
            <p className="text-xs text-surface-400">
              Showing {filtered.length} of {conversations.length} conversations
            </p>
          </div>
        )}
      </Card>

      {/* ── Interactive Delete Confirmation Modal ── */}
      <Modal
        isOpen={Boolean(convToDelete)}
        onClose={() => !isDeleting && setConvToDelete(null)}
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
                Delete conversation permanently?
              </p>
              <p className="text-xs text-surface-500 mt-1 bg-surface-50 p-2 rounded-lg border border-surface-200/60 truncate font-mono">
                "{convToDelete?.title || 'Untitled Conversation'}"
              </p>
              <p className="text-xs text-red-500/90 mt-2">
                This will remove the conversation history and all associated messages.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-surface-200/60">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setConvToDelete(null)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={confirmDelete}
              loading={isDeleting}
            >
              Delete
            </Button>
          </div>
        </div>
      </Modal>
    </motion.div>
  )
}
