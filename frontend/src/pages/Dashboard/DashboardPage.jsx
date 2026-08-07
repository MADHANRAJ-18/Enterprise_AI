import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  MessageSquare, FileUp, TrendingUp, TrendingDown, Minus,
  ArrowRight, Clock, Bot, Plus, CheckCircle2
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { useAuth } from '../../context/AuthContext'
import { Card, CardHeader, CardBody } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { listDocuments } from '../../services/documentService'
import { mockActivityData } from '../../data/mockData'

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

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white/80 backdrop-blur-md rounded-xl border border-white/40 shadow-[0_8px_30px_rgb(0,0,0,0.12)] p-4 min-w-[150px]">
      <p className="text-sm font-bold text-surface-900 mb-3 border-b border-surface-200/60 pb-2">{label}</p>
      <div className="space-y-2.5">
        {payload.map((p) => (
          <div key={p.dataKey} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2.5">
              <div 
                className="w-2.5 h-2.5 rounded-full shadow-sm" 
                style={{ backgroundColor: p.dataKey === 'queries' ? '#3B82F6' : '#10B981' }} 
              />
              <span className="text-surface-600 font-medium capitalize">{p.name || p.dataKey}</span>
            </div>
            <span className="font-bold text-surface-900">{p.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { user, getUserDisplayName } = useAuth()
  const navigate = useNavigate()
  const firstName = getUserDisplayName().split(' ')[0]

  const [docStats, setDocStats] = useState({ total: 0, indexed: 0 })

  useEffect(() => {
    if (!user?.id) return
    listDocuments(user.id).then(({ data }) => {
      if (data) {
        setDocStats({
          total: data.length,
          indexed: data.filter((d) => d.status === 'Indexed').length,
        })
      }
    })
  }, [user?.id])

  const metrics = [
    { label: 'Total Chats', value: '0', change: '0%', trend: 'neutral' },
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
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-surface-900">Activity Overview</h2>
                  <p className="text-xs text-surface-400 mt-0.5">Queries & documents — last 7 days</p>
                </div>
                <Badge variant="blue">This week</Badge>
              </div>
            </CardHeader>
            <CardBody className="pt-2">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={mockActivityData} margin={{ top: 20, right: 5, left: -20, bottom: 0 }} barGap={6}>
                  <defs>
                    <linearGradient id="colorQueries" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3B82F6" stopOpacity={1} />
                      <stop offset="100%" stopColor="#2563EB" stopOpacity={0.8} />
                    </linearGradient>
                    <linearGradient id="colorDocs" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10B981" stopOpacity={1} />
                      <stop offset="100%" stopColor="#059669" stopOpacity={0.8} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 12, fill: '#94a3b8', fontWeight: 500 }} axisLine={false} tickLine={false} dy={10} />
                  <YAxis tick={{ fontSize: 12, fill: '#94a3b8', fontWeight: 500 }} axisLine={false} tickLine={false} dx={-10} />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f8fafc' }} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 13, paddingTop: 20, fontWeight: 500 }} />
                  <Bar dataKey="queries" name="Queries" fill="url(#colorQueries)" radius={[4, 4, 0, 0]} barSize={14} />
                  <Bar dataKey="documents" name="Documents" fill="url(#colorDocs)" radius={[4, 4, 0, 0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            </CardBody>
          </Card>
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
