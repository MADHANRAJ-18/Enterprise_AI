import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, Bell, ChevronDown, User, Settings, LogOut,
  FileText, Check, Moon, Sun, CheckCheck
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../context/ThemeContext'
import { Avatar } from '../ui/Avatar'
import {
  fetchNotifications,
  markNotificationAsRead,
  markAllNotificationsAsRead,
  subscribeToNotifications,
} from '../../services/notificationService'

function formatNotificationTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMinutes = Math.floor((now - date) / 60000)
  if (diffMinutes < 1) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function NotificationPanel({
  notifications,
  unreadCount,
  onMarkAsRead,
  onMarkAllAsRead,
  onClose,
}) {
  const navigate = useNavigate()

  const handleNotificationClick = async (notif) => {
    if (!notif.is_read) {
      await onMarkAsRead(notif.id)
    }
    navigate('/documents')
    onClose()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.96 }}
      transition={{ duration: 0.15 }}
      className="absolute right-0 top-full mt-2 w-84 bg-surface-100 rounded-2xl shadow-2xl border border-surface-200/60 z-50 overflow-hidden"
    >
      <div className="px-4 py-3 border-b border-surface-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-surface-900">Notifications</h3>
          {unreadCount > 0 && (
            <span className="px-1.5 py-0.5 rounded-md text-[11px] font-bold bg-primary-100 text-primary-700">
              {unreadCount} new
            </span>
          )}
        </div>
        {unreadCount > 0 && (
          <button
            onClick={onMarkAllAsRead}
            className="flex items-center gap-1 text-xs font-medium text-surface-500 hover:text-primary-600 transition-colors"
          >
            <CheckCheck size={14} /> Mark all read
          </button>
        )}
      </div>

      <div className="max-h-80 overflow-y-auto divide-y divide-surface-100">
        {notifications.length > 0 ? (
          notifications.map((n) => (
            <div
              key={n.id}
              onClick={() => handleNotificationClick(n)}
              className={`flex gap-3 px-4 py-3 hover:bg-surface-50 transition-colors cursor-pointer ${
                !n.is_read ? 'bg-primary-50/25' : ''
              }`}
            >
              <div className="flex-shrink-0 mt-0.5 p-1.5 rounded-lg bg-primary-100 text-primary-600">
                <FileText size={14} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-1">
                  <p className="text-xs font-semibold text-surface-900 truncate">{n.title}</p>
                  <span className="text-[10px] text-surface-400 flex-shrink-0">
                    {formatNotificationTime(n.created_at)}
                  </span>
                </div>
                <p className="text-xs text-surface-600 mt-0.5 leading-relaxed">{n.message}</p>
              </div>
              {!n.is_read && (
                <div className="w-2 h-2 rounded-full bg-primary-500 flex-shrink-0 mt-1.5" />
              )}
            </div>
          ))
        ) : (
          <div className="p-6 text-center text-xs text-surface-400">
            No notifications yet
          </div>
        )}
      </div>

      <div className="px-4 py-2.5 border-t border-surface-100 text-center bg-surface-50/50">
        <button
          onClick={() => {
            navigate('/documents')
            onClose()
          }}
          className="text-xs font-medium text-primary-600 hover:text-primary-700 transition-colors"
        >
          View Company Documents
        </button>
      </div>
    </motion.div>
  )
}

function UserMenu({ onClose }) {
  const { getUserDisplayName, getUserAvatar, signOut } = useAuth()
  const { user } = useAuth()
  const navigate = useNavigate()

  const handleSignOut = async () => {
    await signOut()
    navigate('/login')
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.96 }}
      transition={{ duration: 0.15 }}
      className="absolute right-0 top-full mt-2 w-64 bg-surface-100 rounded-2xl shadow-2xl border border-surface-200/60 z-50 overflow-hidden"
    >
      <div className="px-4 py-4 border-b border-surface-100">
        <div className="flex items-center gap-3">
          <Avatar src={getUserAvatar()} name={getUserDisplayName()} size="lg" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-surface-900 truncate">{getUserDisplayName()}</p>
            <p className="text-xs text-surface-500 truncate">{user?.email}</p>
          </div>
        </div>
      </div>
      <div className="p-2">
        <button
          onClick={() => { navigate('/profile'); onClose() }}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-surface-700 hover:bg-surface-100 transition-colors"
        >
          <User size={16} className="text-surface-400" /> Profile
        </button>
        <button
          onClick={() => { navigate('/settings'); onClose() }}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-surface-700 hover:bg-surface-100 transition-colors"
        >
          <Settings size={16} className="text-surface-400" /> Settings
        </button>
        <div className="my-1 border-t border-surface-100" />
        <button
          onClick={handleSignOut}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-red-600 hover:bg-red-50 transition-colors"
        >
          <LogOut size={16} className="text-red-400" /> Sign Out
        </button>
      </div>
    </motion.div>
  )
}

export function Navbar() {
  const { user, getUserDisplayName, getUserAvatar } = useAuth()
  const { isDark, toggleTheme } = useTheme()
  const [showNotifs, setShowNotifs] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [search, setSearch] = useState('')
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const notifsRef = useRef(null)
  const menuRef = useRef(null)

  // ── Load Notifications ─────────────────────────────────────
  const loadNotifications = useCallback(async () => {
    if (!user?.id) return
    const { data, unreadCount: count } = await fetchNotifications(user.id, { limit: 20 })
    setNotifications(data || [])
    setUnreadCount(count || 0)
  }, [user?.id])

  useEffect(() => {
    loadNotifications()

    if (!user?.id) return
    // Subscribe to realtime changes in notifications table
    const unsubscribe = subscribeToNotifications(user.id, () => {
      loadNotifications()
    })

    return () => {
      if (typeof unsubscribe === 'function') unsubscribe()
    }
  }, [user?.id, loadNotifications])

  // ── Mark as Read Handlers ──────────────────────────────────
  const handleMarkAsRead = async (notificationId) => {
    if (!user?.id) return
    await markNotificationAsRead(user.id, notificationId)
    setNotifications((prev) =>
      prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
    )
    setUnreadCount((prev) => Math.max(0, prev - 1))
  }

  const handleMarkAllAsRead = async () => {
    if (!user?.id) return
    await markAllNotificationsAsRead(user.id)
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    setUnreadCount(0)
  }

  // ── Close dropdowns on outside click ───────────────────────
  useEffect(() => {
    const handler = (e) => {
      if (notifsRef.current && !notifsRef.current.contains(e.target)) setShowNotifs(false)
      if (menuRef.current && !menuRef.current.contains(e.target)) setShowMenu(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <header className="sticky top-0 z-40 h-16 flex items-center px-6 bg-surface-50/95 backdrop-blur-sm border-b border-surface-200 shadow-nav flex-shrink-0">
      {/* Search */}
      <div className="flex-1 max-w-md">
        <div className="relative flex items-center">
          <Search size={16} className="absolute left-3 text-surface-400 pointer-events-none" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations, documents..."
            className="w-full pl-9 pr-4 py-2 text-sm bg-surface-100 border border-transparent rounded-xl outline-none transition-all duration-150 placeholder:text-surface-400 focus:bg-white focus:border-primary-300 focus:ring-2 focus:ring-primary-500/20"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 ml-4">
        {/* Notification bell */}
        <div ref={notifsRef} className="relative">
          <button
            id="notifications-btn"
            onClick={() => { setShowNotifs((p) => !p); setShowMenu(false) }}
            className="relative p-2 rounded-xl text-surface-500 hover:bg-surface-100 hover:text-surface-800 transition-colors"
            title="Notifications"
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 min-w-4 h-4 px-1 rounded-full bg-primary-600 text-white text-[10px] font-bold flex items-center justify-center shadow-sm">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>
          <AnimatePresence>
            {showNotifs && (
              <NotificationPanel
                notifications={notifications}
                unreadCount={unreadCount}
                onMarkAsRead={handleMarkAsRead}
                onMarkAllAsRead={handleMarkAllAsRead}
                onClose={() => setShowNotifs(false)}
              />
            )}
          </AnimatePresence>
        </div>

        {/* Theme toggle */}
        <motion.button
          id="theme-toggle-btn"
          onClick={toggleTheme}
          whileTap={{ scale: 0.9 }}
          className="p-2 rounded-xl text-surface-500 hover:bg-surface-100 hover:text-surface-800 transition-colors"
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          <AnimatePresence mode="wait" initial={false}>
            {isDark ? (
              <motion.div key="sun" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.2 }}>
                <Sun size={18} />
              </motion.div>
            ) : (
              <motion.div key="moon" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.2 }}>
                <Moon size={18} />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.button>

        {/* Divider */}
        <div className="w-px h-6 bg-surface-200 mx-1" />

        {/* User menu */}
        <div ref={menuRef} className="relative">
          <button
            id="user-menu-btn"
            onClick={() => { setShowMenu((p) => !p); setShowNotifs(false) }}
            className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl hover:bg-surface-100 transition-colors"
          >
            <Avatar src={getUserAvatar()} name={getUserDisplayName()} size="sm" />
            <span className="text-sm font-medium text-surface-800 hidden sm:block max-w-[120px] truncate">
              {getUserDisplayName()}
            </span>
            <ChevronDown size={14} className="text-surface-400 hidden sm:block" />
          </button>
          <AnimatePresence>
            {showMenu && <UserMenu onClose={() => setShowMenu(false)} />}
          </AnimatePresence>
        </div>
      </div>
    </header>
  )
}
