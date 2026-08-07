import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Bell, ChevronDown, User, Settings, LogOut, CheckCircle, XCircle, Info, Moon, Sun } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../context/ThemeContext'
import { Avatar } from '../ui/Avatar'
import { mockNotifications } from '../../data/mockData'

function NotificationPanel({ onClose }) {
  const unreadCount = mockNotifications.filter((n) => !n.read).length
  const typeIcon = {
    success: <CheckCircle size={14} className="text-emerald-500" />,
    error: <XCircle size={14} className="text-red-500" />,
    info: <Info size={14} className="text-primary-500" />,
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.96 }}
      transition={{ duration: 0.15 }}
      className="absolute right-0 top-full mt-2 w-80 bg-surface-100 rounded-2xl shadow-2xl border border-surface-200/60 z-50 overflow-hidden"
    >
      <div className="px-4 py-3 border-b border-surface-100 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-surface-900">Notifications</h3>
        {unreadCount > 0 && (
          <span className="text-xs font-medium text-primary-600">{unreadCount} unread</span>
        )}
      </div>
      <div className="max-h-80 overflow-y-auto divide-y divide-surface-100">
        {mockNotifications.length > 0 ? (
          mockNotifications.map((n) => (
            <div key={n.id} className={`flex gap-3 px-4 py-3 hover:bg-surface-50 transition-colors cursor-pointer ${!n.read ? 'bg-primary-50/30' : ''}`}>
              <div className="flex-shrink-0 mt-0.5">{typeIcon[n.type]}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-surface-900">{n.title}</p>
                <p className="text-xs text-surface-500 mt-0.5 leading-relaxed">{n.message}</p>
                <p className="text-xs text-surface-400 mt-1">{n.time}</p>
              </div>
              {!n.read && <div className="w-2 h-2 rounded-full bg-primary-500 flex-shrink-0 mt-1.5" />}
            </div>
          ))
        ) : (
          <div className="p-6 text-center text-xs text-surface-400">
            No notifications yet
          </div>
        )}
      </div>
      <div className="px-4 py-2.5 border-t border-surface-100 text-center">
        <button className="text-xs font-medium text-primary-600 hover:text-primary-700 transition-colors">
          View all notifications
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
      {/* User info */}
      <div className="px-4 py-4 border-b border-surface-100">
        <div className="flex items-center gap-3">
          <Avatar src={getUserAvatar()} name={getUserDisplayName()} size="lg" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-surface-900 truncate">{getUserDisplayName()}</p>
            <p className="text-xs text-surface-500 truncate">{user?.email}</p>
          </div>
        </div>
      </div>
      {/* Menu items */}
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
  const { getUserDisplayName, getUserAvatar } = useAuth()
  const { isDark, toggleTheme } = useTheme()
  const [showNotifs, setShowNotifs] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [search, setSearch] = useState('')
  const notifsRef = useRef(null)
  const menuRef = useRef(null)
  const unreadCount = mockNotifications.filter((n) => !n.read).length

  // Close dropdowns on outside click
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
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </button>
          <AnimatePresence>
            {showNotifs && <NotificationPanel onClose={() => setShowNotifs(false)} />}
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
