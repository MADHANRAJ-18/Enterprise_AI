import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, Filter, MessageSquare, Clock, ChevronDown,
  ChevronUp, Download, Calendar, Bot, Tag
} from 'lucide-react'
import { Card, CardHeader, CardBody } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { mockConversations, mockMessages } from '../../data/mockData'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

function ConversationRow({ conv }) {
  const [expanded, setExpanded] = useState(false)
  const messages = mockMessages[conv.id] || []

  return (
    <motion.div layout className="border-b border-surface-100 last:border-0">
      <button
        className="w-full text-left px-5 py-4 hover:bg-surface-50 transition-colors group"
        onClick={() => setExpanded((p) => !p)}
      >
        <div className="flex items-start gap-4">
          <div className="w-9 h-9 rounded-xl bg-primary-50 flex items-center justify-center flex-shrink-0 mt-0.5">
            <MessageSquare size={16} className="text-primary-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-surface-900 group-hover:text-primary-600 transition-colors truncate">
                {conv.title}
              </p>
              <div className="flex items-center gap-3 flex-shrink-0">
                <div className="flex items-center gap-1 text-xs text-surface-400">
                  <Clock size={11} />
                  {formatDate(conv.createdAt)}
                </div>
                {expanded ? (
                  <ChevronUp size={15} className="text-surface-400" />
                ) : (
                  <ChevronDown size={15} className="text-surface-400" />
                )}
              </div>
            </div>
            <p className="text-xs text-surface-500 mt-0.5 truncate">{conv.preview}</p>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <div className="flex items-center gap-1">
                <Bot size={11} className="text-surface-400" />
                <Badge variant="gray">{conv.agent}</Badge>
              </div>
              <span className="text-xs text-surface-400">{conv.messages} messages</span>
              {conv.tags.map((tag) => (
                <div key={tag} className="flex items-center gap-1">
                  <Tag size={10} className="text-primary-400" />
                  <Badge variant="blue">{tag}</Badge>
                </div>
              ))}
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
              <p className="text-xs font-semibold text-surface-400 uppercase tracking-wide mb-3">Conversation Preview</p>
              {messages.length > 0 ? (
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
                      <p className="line-clamp-2">{msg.content.substring(0, 120)}{msg.content.length > 120 ? '…' : ''}</p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-surface-400 italic">No message preview available.</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export function HistoryPage() {
  const [search, setSearch] = useState('')
  const [agentFilter, setAgentFilter] = useState('all')
  const [sortOrder, setSortOrder] = useState('newest')

  const agents = ['all', ...new Set(mockConversations.map((c) => c.agent))]

  const filtered = mockConversations
    .filter((c) => {
      const matchSearch = c.title.toLowerCase().includes(search.toLowerCase()) || c.preview.toLowerCase().includes(search.toLowerCase())
      const matchAgent = agentFilter === 'all' || c.agent === agentFilter
      return matchSearch && matchAgent
    })
    .sort((a, b) => {
      if (sortOrder === 'newest') return new Date(b.createdAt) - new Date(a.createdAt)
      if (sortOrder === 'oldest') return new Date(a.createdAt) - new Date(b.createdAt)
      if (sortOrder === 'messages') return b.messages - a.messages
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
          <p className="text-sm text-surface-500 mt-0.5">{mockConversations.length} total conversations</p>
        </div>
        <Button variant="secondary" size="sm">
          <Download size={14} /> Export CSV
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold text-surface-900">{mockConversations.length}</p>
          <p className="text-xs text-surface-500 font-medium mt-0.5">Total Conversations</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold text-surface-900">{mockConversations.reduce((sum, c) => sum + c.messages, 0)}</p>
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

            {/* Agent filter */}
            <div className="relative">
              <select
                value={agentFilter}
                onChange={(e) => setAgentFilter(e.target.value)}
                className="pl-3 pr-8 py-2 text-sm bg-surface-100 border border-transparent rounded-lg outline-none focus:bg-surface-50 focus:border-primary-300 transition-all appearance-none cursor-pointer"
              >
                {agents.map((a) => (
                  <option key={a} value={a}>{a === 'all' ? 'All Agents' : a}</option>
                ))}
              </select>
              <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-400 pointer-events-none" />
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
                <option value="messages">Most Messages</option>
              </select>
              <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-400 pointer-events-none" />
            </div>
          </div>
        </CardHeader>

        <div>
          {filtered.length > 0 ? (
            filtered.map((conv) => <ConversationRow key={conv.id} conv={conv} />)
          ) : (
            <div className="py-16 text-center">
              <MessageSquare size={32} className="text-surface-300 mx-auto mb-3" />
              <p className="text-sm font-medium text-surface-500">No conversations found</p>
              <p className="text-xs text-surface-400 mt-1">Try adjusting your search or filters</p>
            </div>
          )}
        </div>

        {filtered.length > 0 && (
          <div className="px-5 py-3 border-t border-surface-100 bg-surface-50/50 rounded-b-xl">
            <p className="text-xs text-surface-400">Showing {filtered.length} of {mockConversations.length} conversations</p>
          </div>
        )}
      </Card>
    </motion.div>
  )
}
