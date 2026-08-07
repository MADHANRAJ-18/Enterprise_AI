import { NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, MessageSquare, FileUp, History,
  User, Settings, ChevronLeft, ChevronRight, Bot, Zap
} from 'lucide-react'
import { useSidebar } from '../../context/SidebarContext'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/chat', icon: MessageSquare, label: 'AI Chat' },
  { to: '/documents', icon: FileUp, label: 'Documents' },
  { to: '/history', icon: History, label: 'History' },
]

const bottomItems = [
  { to: '/profile', icon: User, label: 'Profile' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

function NavItem({ to, icon: Icon, label, collapsed }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
         ${isActive
          ? 'bg-primary-600 text-white shadow-sm'
          : 'text-surface-600 hover:bg-surface-100 hover:text-surface-900'
        } ${collapsed ? 'justify-center' : ''}`
      }
    >
      {({ isActive }) => (
        <>
          <Icon size={18} className={isActive ? 'text-white' : 'text-surface-500'} />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                className="whitespace-nowrap overflow-hidden"
              >
                {label}
              </motion.span>
            )}
          </AnimatePresence>
        </>
      )}
    </NavLink>
  )
}

export function Sidebar() {
  const { collapsed, toggle } = useSidebar()

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 240 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      className="relative flex flex-col h-screen bg-surface-100 border-r border-surface-200 flex-shrink-0 overflow-hidden"
    >
      {/* Logo */}
      <div className={`flex items-center h-16 px-4 border-b border-surface-100 flex-shrink-0 ${collapsed ? 'justify-center' : 'gap-3'}`}>
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary-600 to-primary-800 flex items-center justify-center flex-shrink-0">
          <Bot size={16} className="text-white" />
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="overflow-hidden"
            >
              <span className="text-sm font-bold text-surface-900 whitespace-nowrap">Enterprise AI</span>
              <div className="flex items-center gap-1 mt-0.5">
                <Zap size={10} className="text-primary-500" />
                <span className="text-xs text-surface-400 whitespace-nowrap">Multi-Agent Platform</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <AnimatePresence>
          {!collapsed && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="px-3 mb-2 text-[11px] font-semibold text-surface-400 uppercase tracking-wider"
            >
              Main
            </motion.p>
          )}
        </AnimatePresence>
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} collapsed={collapsed} />
        ))}

        <div className="pt-4">
          <AnimatePresence>
            {!collapsed && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="px-3 mb-2 text-[11px] font-semibold text-surface-400 uppercase tracking-wider"
              >
                Account
              </motion.p>
            )}
          </AnimatePresence>
          {bottomItems.map((item) => (
            <NavItem key={item.to} {...item} collapsed={collapsed} />
          ))}
        </div>
      </nav>

      {/* Collapse toggle */}
      <div className="px-3 py-3 border-t border-surface-100">
        <button
          onClick={toggle}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-surface-500 hover:bg-surface-100 hover:text-surface-700 transition-all duration-150 ${collapsed ? 'justify-center' : ''}`}
        >
          {collapsed ? <ChevronRight size={16} /> : (
            <>
              <ChevronLeft size={16} />
              <span className="text-sm font-medium whitespace-nowrap">Collapse</span>
            </>
          )}
        </button>
      </div>
    </motion.aside>
  )
}
