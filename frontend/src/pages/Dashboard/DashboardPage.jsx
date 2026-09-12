import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  MessageSquare, FileUp, TrendingUp, TrendingDown, Minus,
  ArrowRight, Clock, Bot, Plus, CheckCircle2, Activity,
  BarChart2, LineChart as LineChartIcon, Layers, Zap
} from 'lucide-react'
import {
  BarChart, Bar, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { useAuth } from '../../context/AuthContext'
import { supabase } from '../../lib/supabaseClient'
import { Card, CardHeader, CardBody } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { listDocuments } from '../../services/documentService'

const pageVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.4, 0, 0.2, 1] } },
}

const stagger = {
  visible: { transition: { staggerChildren: 0.07 } },
}

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35 } },
}

const metricIcons = [MessageSquare, FileUp, CheckCircle2, Bot]
const metricColors = [
  'bg-primary-50 dark:bg-primary-950/40 text-primary-600 dark:text-primary-400',
  'bg-violet-50 dark:bg-violet-950/40 text-violet-600 dark:text-violet-400',
  'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400',
  'bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400',
]

// ── Real Activity Data Builder ────────────────────────────────
function buildRealActivityData(documents = [], conversations = [], timeRange = '7d') {
  const daysCount = timeRange === '7d' ? 7 : 30
  const now = new Date()

  // Generate date slots for last N days
  const slots = []
  for (let i = daysCount - 1; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const dateStr = d.toISOString().split('T')[0] // 'YYYY-MM-DD'
    const dayLabel = daysCount === 7 
      ? d.toLocaleDateString('en-US', { weekday: 'short' })
      : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    
    slots.push({ dateStr, day: dayLabel, queries: 0, documents: 0 })
  }

  const slotMap = new Map(slots.map((s) => [s.dateStr, s]))

  // Map real documents uploaded per day
  documents.forEach((doc) => {
    if (!doc.uploaded_at) return
    const dateStr = new Date(doc.uploaded_at).toISOString().split('T')[0]
    if (slotMap.has(dateStr)) {
      slotMap.get(dateStr).documents += 1
    }
  })

  // Map real conversations/queries created per day
  conversations.forEach((conv) => {
    const ts = conv.created_at || conv.createdAt || conv.timestamp
    if (!ts) return
    const dateStr = new Date(ts).toISOString().split('T')[0]
    if (slotMap.has(dateStr)) {
      slotMap.get(dateStr).queries += 1
    }
  })

  return Array.from(slotMap.values())
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div
      className="rounded-xl border shadow-2xl p-4 min-w-[180px] text-xs font-sans"
      style={{
        backgroundColor: '#0f172a',
        borderColor: '#334155',
        color: '#ffffff',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)'
      }}
    >
      <div
        className="font-bold mb-2.5 pb-2 flex items-center justify-between"
        style={{ borderBottom: '1px solid #334155' }}
      >
        <span className="text-sm" style={{ color: '#f8fafc' }}>{label}</span>
        <span
          className="text-[10px] font-semibold px-2 py-0.5 rounded-full border"
          style={{
            backgroundColor: 'rgba(59, 130, 246, 0.2)',
            color: '#93c5fd',
            borderColor: 'rgba(59, 130, 246, 0.4)'
          }}
        >
          Analytics
        </span>
      </div>
      <div className="space-y-2">
        {payload.map((p) => (
          <div key={p.dataKey} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div
                className="w-2.5 h-2.5 rounded-full shadow-sm"
                style={{ backgroundColor: p.color || (p.dataKey === 'queries' ? '#3B82F6' : '#10B981') }}
              />
              <span className="font-medium capitalize" style={{ color: '#cbd5e1' }}>
                {p.name || p.dataKey}
              </span>
            </div>
            <span className="font-bold text-sm" style={{ color: '#ffffff' }}>
              {p.value} {p.dataKey === 'latency' ? 'ms' : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function MetricCard({ label, value, change, trend, icon: Icon, color }) {
  const trendIcon = trend === 'up'
    ? <TrendingUp size={12} className="text-emerald-600" />
    : trend === 'down'
    ? <TrendingDown size={12} className="text-red-600" />
    : <Minus size={12} className="text-surface-400" />
  const trendColor = trend === 'up' ? 'text-emerald-600' : trend === 'down' ? 'text-red-600' : 'text-surface-400'

  return (
    <motion.div variants={fadeUp}>
      <Card className="p-5 hover:shadow-card-hover transition-shadow duration-200">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-surface-500 font-medium">{label}</p>
            <p className="text-3xl font-bold text-surface-900 mt-1">{value}</p>
          </div>
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
            <Icon size={20} />
          </div>
        </div>
        <div className="flex items-center gap-1.5 mt-3">
          {trendIcon}
          <span className={`text-xs font-semibold ${trendColor}`}>{change}</span>
          <span className="text-xs text-surface-400">vs last week</span>
        </div>
      </Card>
    </motion.div>
  )
}

// ── Interactive Activity Chart Component ─────────────────────
function InteractiveActivityChart({ documents = [], conversations = [] }) {
  const [chartType, setChartType] = useState('area') // 'area' | 'bar' | 'line'
  const [timeRange, setTimeRange] = useState('7d')   // '7d' | '30d'

  const data = buildRealActivityData(documents, conversations, timeRange)

  return (
    <Card className="overflow-hidden border border-surface-200 dark:border-surface-700/60 shadow-lg">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-base font-bold text-surface-900 flex items-center gap-2">
              <Activity size={18} className="text-primary-400" />
              Activity Overview
            </h2>
            <p className="text-xs text-surface-400 mt-0.5">Interactive RAG queries & document indexation trends</p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Time range pills */}
            <div className="flex items-center gap-1 bg-surface-200/80 dark:bg-surface-800 p-1 rounded-xl">
              <button
                onClick={() => setTimeRange('7d')}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                  timeRange === '7d'
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-surface-500 hover:text-surface-900'
                }`}
              >
                7 Days
              </button>
              <button
                onClick={() => setTimeRange('30d')}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                  timeRange === '30d'
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-surface-500 hover:text-surface-900'
                }`}
              >
                30 Days
              </button>
            </div>

            {/* Chart type toggle icons */}
            <div className="flex items-center gap-1 bg-surface-200/80 dark:bg-surface-800 p-1 rounded-xl">
              <button
                onClick={() => setChartType('area')}
                title="Area Chart View"
                className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
                  chartType === 'area'
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-surface-500 hover:text-surface-900'
                }`}
              >
                <Layers size={14} />
              </button>
              <button
                onClick={() => setChartType('bar')}
                title="Bar Chart View"
                className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
                  chartType === 'bar'
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-surface-500 hover:text-surface-900'
                }`}
              >
                <BarChart2 size={14} />
              </button>
              <button
                onClick={() => setChartType('line')}
                title="Line Trend View"
                className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
                  chartType === 'line'
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-surface-500 hover:text-surface-900'
                }`}
              >
                <LineChartIcon size={14} />
              </button>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardBody className="pt-2 pb-4">
        <ResponsiveContainer width="100%" height={260}>
          {chartType === 'area' ? (
            <AreaChart data={data} margin={{ top: 20, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="areaQueries" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="areaDocs" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10B981" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#10B981" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.15)" vertical={false} />
              <XAxis dataKey="day" interval={timeRange === '30d' ? 4 : 0} tick={{ fontSize: 12, fill: '#94a3b8', fontWeight: 500 }} axisLine={false} tickLine={false} dy={8} />
              <YAxis tick={{ fontSize: 12, fill: '#94a3b8', fontWeight: 500 }} axisLine={false} tickLine={false} dx={-8} />
              <Tooltip content={<CustomTooltip />} wrapperStyle={{ outline: 'none', backgroundColor: 'transparent' }} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 16 }} />
              <Area type="monotone" dataKey="queries" name="Queries" stroke="#3B82F6" strokeWidth={3} fillOpacity={1} fill="url(#areaQueries)" activeDot={{ r: 6 }} />
              <Area type="monotone" dataKey="documents" name="Documents" stroke="#10B981" strokeWidth={3} fillOpacity={1} fill="url(#areaDocs)" activeDot={{ r: 6 }} />
            </AreaChart>
          ) : chartType === 'bar' ? (
            <BarChart data={data} margin={{ top: 20, right: 10, left: -20, bottom: 0 }} barGap={6}>
              <defs>
                <linearGradient id="barQueries" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3B82F6" stopOpacity={1} />
                  <stop offset="100%" stopColor="#1D4ED8" stopOpacity={0.8} />
                </linearGradient>
                <linearGradient id="barDocs" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10B981" stopOpacity={1} />
                  <stop offset="100%" stopColor="#047857" stopOpacity={0.8} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.15)" vertical={false} />
              <XAxis dataKey="day" interval={timeRange === '30d' ? 4 : 0} tick={{ fontSize: 12, fill: '#94a3b8', fontWeight: 500 }} axisLine={false} tickLine={false} dy={8} />
              <YAxis tick={{ fontSize: 12, fill: '#94a3b8', fontWeight: 500 }} axisLine={false} tickLine={false} dx={-8} />
              <Tooltip content={<CustomTooltip />} wrapperStyle={{ outline: 'none', backgroundColor: 'transparent' }} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 16 }} />
              <Bar dataKey="queries" name="Queries" fill="url(#barQueries)" radius={[6, 6, 0, 0]} barSize={16} />
              <Bar dataKey="documents" name="Documents" fill="url(#barDocs)" radius={[6, 6, 0, 0]} barSize={16} />
            </BarChart>
          ) : (
            <LineChart data={data} margin={{ top: 20, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.15)" vertical={false} />
              <XAxis dataKey="day" interval={timeRange === '30d' ? 4 : 0} tick={{ fontSize: 12, fill: '#94a3b8', fontWeight: 500 }} axisLine={false} tickLine={false} dy={8} />
              <YAxis tick={{ fontSize: 12, fill: '#94a3b8', fontWeight: 500 }} axisLine={false} tickLine={false} dx={-8} />
              <Tooltip content={<CustomTooltip />} wrapperStyle={{ outline: 'none', backgroundColor: 'transparent' }} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 16 }} />
              <Line type="monotone" dataKey="queries" name="Queries" stroke="#3B82F6" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 7 }} />
              <Line type="monotone" dataKey="documents" name="Documents" stroke="#10B981" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 7 }} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </CardBody>
    </Card>
  )
}

export function DashboardPage() {
  const { user, getUserDisplayName } = useAuth()
  const navigate = useNavigate()
  const firstName = getUserDisplayName().split(' ')[0]

  const [docList, setDocList] = useState([])
  const [convList, setConvList] = useState([])
  const [docStats, setDocStats] = useState({ total: 0, indexed: 0 })

  useEffect(() => {
    if (!user?.id) return
    listDocuments(user.id).then(({ data }) => {
      if (data) {
        setDocList(data)
        setDocStats({
          total: data.length,
          indexed: data.filter((d) => d.status === 'Indexed').length,
        })
      }
    })

    // Fetch user's real conversations/messages from Supabase
    supabase
      .from('conversations')
      .select('created_at')
      .eq('user_id', user.id)
      .then(({ data }) => {
        if (data) setConvList(data)
      })
      .catch(() => {})
  }, [user?.id])

  const metrics = [
    { label: 'Total Chats', value: convList.length.toString(), change: '0%', trend: 'neutral' },
    { label: 'Documents Uploaded', value: docStats.total.toString(), change: '0%', trend: 'neutral' },
    { label: 'Documents Indexed', value: docStats.indexed.toString(), change: '0%', trend: 'neutral' },
    { label: 'Agents Active', value: '1', change: '0%', trend: 'neutral' },
  ]

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={pageVariants}
      className="p-6 max-w-7xl mx-auto space-y-6"
    >
      {/* Welcome banner */}
      <motion.div
        variants={fadeUp}
        className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary-600 via-primary-700 to-primary-900 p-6 text-white"
      >
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 right-0 w-64 h-64 rounded-full bg-white/30 -translate-y-1/2 translate-x-1/4" />
          <div className="absolute bottom-0 left-0 w-48 h-48 rounded-full bg-white/20 translate-y-1/2 -translate-x-1/4" />
        </div>
        <div className="relative flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold">Good morning, {firstName} 👋</h1>
            <p className="text-primary-200 mt-1 text-sm">
              Your AI workspace is ready. {docStats.total} total documents, {docStats.indexed} indexed and queryable.
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              variant="secondary"
              onClick={() => navigate('/documents')}
              className="!bg-white/20 !border-white/30 !text-white hover:!bg-white/30"
            >
              <FileUp size={16} /> Upload Docs
            </Button>
            <Button
              variant="secondary"
              onClick={() => navigate('/chat')}
              className="!bg-white !text-primary-700 hover:!bg-primary-50"
            >
              <Plus size={16} /> New Chat
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Metrics */}
      <motion.div variants={stagger} initial="hidden" animate="visible" className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((m, i) => (
          <MetricCard
            key={m.label}
            {...m}
            icon={metricIcons[i]}
            color={metricColors[i]}
          />
        ))}
      </motion.div>

      {/* Activity chart — full width */}
      <motion.div variants={fadeUp}>
        <InteractiveActivityChart documents={docList} conversations={convList} />
      </motion.div>

      {/* Recent conversations */}
      <motion.div variants={fadeUp}>
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-surface-900">Recent Conversations</h2>
                <p className="text-xs text-surface-400 mt-0.5">Your latest AI interactions</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => navigate('/history')}>
                View all <ArrowRight size={14} />
              </Button>
            </div>
          </CardHeader>
          <div className="p-8 text-center">
            <div className="w-12 h-12 rounded-2xl bg-primary-50 dark:bg-primary-950/40 text-primary-600 dark:text-primary-400 flex items-center justify-center mx-auto mb-3">
              <MessageSquare size={22} />
            </div>
            <h3 className="text-sm font-semibold text-surface-900 mb-1">No conversations yet</h3>
            <p className="text-xs text-surface-400 max-w-sm mx-auto mb-4">
              Start a new chat to ask questions and extract insights from your indexed documents.
            </p>
            <Button size="sm" onClick={() => navigate('/chat')}>
              <Plus size={14} /> Start New Chat
            </Button>
          </div>
        </Card>
      </motion.div>
    </motion.div>
  )
}
