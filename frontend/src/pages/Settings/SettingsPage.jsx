import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bot, Bell, Shield, Save, RotateCcw, CheckCircle,
  Key, RefreshCw, AlertCircle, Lock, Eye, EyeOff
} from 'lucide-react'
import { Card, CardHeader, CardBody } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Modal } from '../../components/ui/Modal'
import { checkRAGHealth } from '../../services/chatService'
import { useAuth } from '../../context/AuthContext'
import { fetchUserPreferences, updateUserPreferences } from '../../services/notificationService'
import { supabase } from '../../lib/supabaseClient'

const SETTINGS_STORAGE_KEY = 'enterprise_ai_settings'

const DEFAULT_SETTINGS = {
  defaultAgent: 'llama-3.3-70b-versatile',
  responseStyle: 'balanced',
  streamingEnabled: true,
  ragEnabled: true,
  citationsEnabled: true,
  companyFileUpdates: true,
  sessionTimeout: '30',
  apiLogging: true,
}

function Toggle({ checked, onChange, disabled = false }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={`relative inline-flex w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
        disabled ? 'opacity-50 cursor-not-allowed bg-surface-300' : checked ? 'bg-primary-600' : 'bg-surface-300'
      }`}
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 700, damping: 30 }}
        className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm"
        animate={{ x: checked ? 20 : 0 }}
      />
    </button>
  )
}

function SettingRow({ label, description, children }) {
  return (
    <div className="flex items-center justify-between py-4 border-b border-surface-100 last:border-0">
      <div className="flex-1 pr-8">
        <p className="text-sm font-medium text-surface-900">{label}</p>
        {description && <p className="text-xs text-surface-500 mt-0.5">{description}</p>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  )
}

const sections = [
  { id: 'ai', label: 'AI Preferences', icon: Bot },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'security', label: 'Security', icon: Shield },
]

function SaveToast({ show, message = 'Settings saved!' }) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 16, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 16, scale: 0.9 }}
          className="fixed bottom-6 right-6 flex items-center gap-2 bg-emerald-600 text-white px-4 py-2.5 rounded-xl shadow-lg z-50 text-sm font-medium"
        >
          <CheckCircle size={16} /> {message}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function SettingsPage() {
  const { user } = useAuth()
  const isGoogleUser = Boolean(
    user?.app_metadata?.provider === 'google' ||
    user?.app_metadata?.providers?.includes('google') ||
    user?.identities?.some((id) => id.provider === 'google')
  )
  const [activeSection, setActiveSection] = useState('ai')
  const [saved, setSaved] = useState(false)
  const [toastMsg, setToastMsg] = useState('Settings saved!')
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)

  // ── Tab 1: AI Health State ─────────────────────────────────
  const [healthLoading, setHealthLoading] = useState(false)
  const [healthResult, setHealthResult] = useState(null)
  const [healthError, setHealthError] = useState(null)

  // ── Tab 3: Security State ──────────────────────────────────
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false)
  const [passwordData, setPasswordData] = useState({ current: '', newPass: '', confirm: '' })
  const [showPass, setShowPass] = useState(false)
  const [passwordStatus, setPasswordStatus] = useState({ loading: false, error: null, success: null })

  // ── Load & Sync Settings ───────────────────────────────────
  useEffect(() => {
    try {
      const savedSettings = localStorage.getItem(SETTINGS_STORAGE_KEY)
      if (savedSettings) {
        setSettings((prev) => ({ ...prev, ...JSON.parse(savedSettings) }))
      }
    } catch (e) {
      console.error('Failed to parse settings from localStorage', e)
    }

    // Load user preferences from Supabase
    if (user?.id) {
      fetchUserPreferences(user.id).then(({ company_file_updates }) => {
        setSettings((prev) => ({
          ...prev,
          companyFileUpdates: company_file_updates !== false,
        }))
      })
    }
  }, [user?.id])

  const triggerToast = (msg = 'Settings saved!') => {
    setToastMsg(msg)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const set = (key) => (val) => setSettings((prev) => ({ ...prev, [key]: val }))
  const setToggle = (key) => (val) => setSettings((prev) => ({ ...prev, [key]: val }))

  const handleSave = async () => {
    // Persist general settings to localStorage
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings))
    window.dispatchEvent(new Event('settings_updated'))

    // Persist notification preference to Supabase user_preferences table
    if (user?.id) {
      try {
        await updateUserPreferences(user.id, {
          company_file_updates: settings.companyFileUpdates,
        })
      } catch (err) {
        console.error('Failed to persist notification preference to Supabase:', err)
      }
    }

    triggerToast('Settings saved successfully!')
  }

  const handleReset = async () => {
    if (window.confirm('Reset all settings to default factory values?')) {
      setSettings(DEFAULT_SETTINGS)
      localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(DEFAULT_SETTINGS))
      window.dispatchEvent(new Event('settings_updated'))
      setHealthResult(null)
      setHealthError(null)

      if (user?.id) {
        try {
          await updateUserPreferences(user.id, {
            company_file_updates: true,
          })
        } catch (err) {
          console.error('Failed to reset notification preference in Supabase:', err)
        }
      }

      triggerToast('All settings reset to defaults!')
    }
  }

  // ── Tab 1 Action: Test AI Connection ──────────────────────
  const handleTestAIConnection = async () => {
    setHealthLoading(true)
    setHealthError(null)
    setHealthResult(null)
    const startTime = performance.now()

    try {
      const res = await checkRAGHealth()
      const latency = Math.round(performance.now() - startTime)
      setHealthResult({ ...res, latency })
    } catch (err) {
      setHealthError(err.message || 'Failed to connect to AI services')
    } finally {
      setHealthLoading(false)
    }
  }

  // ── Tab 3 Actions: Change Password Handler ─────────────────
  const handleChangePassword = async (e) => {
    e.preventDefault()
    setPasswordStatus({ loading: true, error: null, success: null })

    if (passwordData.newPass.length < 6) {
      setPasswordStatus({ loading: false, error: 'New password must be at least 6 characters.', success: null })
      return
    }

    if (passwordData.newPass !== passwordData.confirm) {
      setPasswordStatus({ loading: false, error: 'New password and confirmation do not match.', success: null })
      return
    }

    try {
      const { error } = await supabase.auth.updateUser({ password: passwordData.newPass })
      if (error) throw error

      setPasswordStatus({ loading: false, error: null, success: 'Password updated successfully!' })
      setPasswordData({ current: '', newPass: '', confirm: '' })
      setTimeout(() => {
        setIsPasswordModalOpen(false)
        setPasswordStatus({ loading: false, error: null, success: null })
        triggerToast('Password changed successfully!')
      }, 1500)
    } catch (err) {
      setPasswordStatus({ loading: false, error: err.message || 'Failed to update password.', success: null })
    }
  }

  // ── Section Renderer ───────────────────────────────────────
  const renderSection = () => {
    switch (activeSection) {
      case 'ai':
        return (
          <div>
            <SettingRow label="Default AI Agent" description="Active primary LLM model for AI chat">
              <select
                value={settings.defaultAgent}
                onChange={(e) => set('defaultAgent')(e.target.value)}
                className="text-sm bg-surface-100 border border-surface-200 rounded-lg px-3 py-1.5 outline-none focus:ring-2 focus:ring-primary-500/20 text-surface-900 font-medium"
              >
                <option value="llama-3.3-70b-versatile">Enterprise AI</option>
              </select>
            </SettingRow>

            <SettingRow label="Response Style" description="Determines tone and structure of AI responses">
              <select
                value={settings.responseStyle}
                onChange={(e) => set('responseStyle')(e.target.value)}
                className="text-sm bg-surface-100 border border-surface-200 rounded-lg px-3 py-1.5 outline-none focus:ring-2 focus:ring-primary-500/20 text-surface-900 font-medium"
              >
                <option value="concise">Concise & Direct</option>
                <option value="balanced">Balanced (Recommended)</option>
                <option value="detailed">Detailed & Comprehensive</option>
              </select>
            </SettingRow>

            <SettingRow label="Streaming Responses" description="Render AI tokens dynamically as they generate">
              <Toggle checked={settings.streamingEnabled} onChange={setToggle('streamingEnabled')} />
            </SettingRow>

            <SettingRow label="RAG Pipeline Default" description="Enable document retrieval augmentation by default">
              <Toggle checked={settings.ragEnabled} onChange={setToggle('ragEnabled')} />
            </SettingRow>

            <SettingRow label="Source Citations" description="Show document source previews and page citations in chat">
              <Toggle checked={settings.citationsEnabled} onChange={setToggle('citationsEnabled')} />
            </SettingRow>

            {/* Live AI Health Check Card */}
            <div className="mt-6 pt-4 border-t border-surface-100">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-xs font-semibold text-surface-900 uppercase tracking-wider">AI Service Status</h3>
                  <p className="text-xs text-surface-500">Test live connectivity to Groq LLM & FAISS vector store</p>
                </div>
                <Button variant="secondary" size="sm" onClick={handleTestAIConnection} disabled={healthLoading}>
                  <RefreshCw size={13} className={healthLoading ? 'animate-spin' : ''} />
                  {healthLoading ? 'Testing...' : 'Test Connection'}
                </Button>
              </div>

              {healthError && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-2 text-xs text-red-600">
                  <AlertCircle size={14} className="flex-shrink-0" />
                  <span>{healthError}</span>
                </div>
              )}

              {healthResult && (
                <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-emerald-700 flex items-center gap-1.5">
                      <CheckCircle size={14} /> All AI Services Operational
                    </span>
                    <Badge variant="green">{healthResult.latency} ms</Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-2 pt-2 text-[11px] border-t border-emerald-500/20 text-surface-700">
                    <div>
                      <span className="text-surface-500 block">LLM Engine</span>
                      <strong className="text-emerald-700 font-medium">Enterprise AI</strong>
                    </div>
                    <div>
                      <span className="text-surface-500 block">Vector Index</span>
                      <strong className="text-emerald-700 font-medium">
                        {healthResult.components?.vector_store?.vectors ?? 0} Vectors Active
                      </strong>
                    </div>
                    <div>
                      <span className="text-surface-500 block">Embedding Model</span>
                      <strong className="text-emerald-700 font-medium">BAAI/bge-small-en-v1.5</strong>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )

      case 'notifications':
        return (
          <div>
            <SettingRow
              label="Company File Updates"
              description="Notify me when company documents I have access to are added, updated, or removed."
            >
              <Toggle
                checked={settings.companyFileUpdates}
                onChange={setToggle('companyFileUpdates')}
              />
            </SettingRow>
          </div>
        )

      case 'security':
        return (
          <div>
            <SettingRow label="Session Timeout" description="Automatically sign out after period of inactivity">
              <select
                value={settings.sessionTimeout}
                onChange={(e) => set('sessionTimeout')(e.target.value)}
                className="text-sm bg-surface-100 border border-surface-200 rounded-lg px-3 py-1.5 outline-none focus:ring-2 focus:ring-primary-500/20 text-surface-900 font-medium"
              >
                <option value="15">15 minutes</option>
                <option value="30">30 minutes</option>
                <option value="60">1 hour</option>
                <option value="480">8 hours</option>
                <option value="0">Never (Stay signed in)</option>
              </select>
            </SettingRow>

            <SettingRow
              label="Password & Credentials"
              description={
                isGoogleUser
                  ? "Your account authentication is managed securely via Google Sign-In."
                  : "Update your account login password"
              }
            >
              {isGoogleUser ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-100 text-surface-600 border border-surface-200">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"/>
                    <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24z"/>
                    <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 9.99 0 12s.45 3.82 1.25 5.42l4.03-3.15z"/>
                    <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/>
                  </svg>
                  Managed by Google
                </span>
              ) : (
                <Button variant="secondary" size="sm" onClick={() => setIsPasswordModalOpen(true)}>
                  <Key size={13} /> Change Password
                </Button>
              )}
            </SettingRow>
          </div>
        )

      default:
        return null
    }
  }

  const ActiveIcon = sections.find((s) => s.id === activeSection)?.icon || Bot

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="p-6 max-w-5xl mx-auto"
    >
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-surface-900">Settings</h1>
        <p className="text-sm text-surface-500 mt-0.5">Customize your Enterprise AI experience</p>
      </div>

      <div className="flex gap-6">
        {/* Settings Navigation Sidebar */}
        <div className="w-52 flex-shrink-0">
          <nav className="space-y-1">
            {sections.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveSection(id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  activeSection === id
                    ? 'bg-primary-50 text-primary-700 shadow-sm'
                    : 'text-surface-600 hover:bg-surface-100 hover:text-surface-900'
                }`}
              >
                <Icon size={16} className={activeSection === id ? 'text-primary-600' : 'text-surface-400'} />
                {label}
              </button>
            ))}
          </nav>
        </div>

        {/* Main Settings Panel */}
        <div className="flex-1">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <ActiveIcon size={16} className="text-primary-600" />
                <h2 className="text-sm font-semibold text-surface-900">
                  {sections.find((s) => s.id === activeSection)?.label}
                </h2>
              </div>
            </CardHeader>
            <CardBody className="py-0">
              <motion.div
                key={activeSection}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
              >
                {renderSection()}
              </motion.div>
            </CardBody>
            <div className="px-5 py-4 border-t border-surface-100 flex items-center justify-between bg-surface-50/50 rounded-b-2xl">
              <Button variant="ghost" size="sm" onClick={handleReset}>
                <RotateCcw size={14} /> Reset Defaults
              </Button>
              <Button onClick={handleSave}>
                <Save size={14} /> Save Settings
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* ── Modal: Change Password Modal ────────────────────── */}
      <Modal isOpen={isPasswordModalOpen} onClose={() => setIsPasswordModalOpen(false)} title="Change Account Password">
        <form onSubmit={handleChangePassword} className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">New Password</label>
            <div className="relative">
              <input
                type={showPass ? 'text' : 'password'}
                required
                minLength={6}
                value={passwordData.newPass}
                onChange={(e) => setPasswordData({ ...passwordData, newPass: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-surface-300 rounded-xl focus:ring-2 focus:ring-primary-500 outline-none pr-9"
                placeholder="Minimum 6 characters"
              />
              <button
                type="button"
                onClick={() => setShowPass(!showPass)}
                className="absolute right-2.5 top-2.5 text-surface-400 hover:text-surface-600"
              >
                {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">Confirm New Password</label>
            <input
              type={showPass ? 'text' : 'password'}
              required
              value={passwordData.confirm}
              onChange={(e) => setPasswordData({ ...passwordData, confirm: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-surface-300 rounded-xl focus:ring-2 focus:ring-primary-500 outline-none"
              placeholder="Re-enter new password"
            />
          </div>

          {passwordStatus.error && (
            <p className="text-xs text-red-600 font-medium">{passwordStatus.error}</p>
          )}

          {passwordStatus.success && (
            <p className="text-xs text-emerald-600 font-medium flex items-center gap-1">
              <CheckCircle size={14} /> {passwordStatus.success}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" type="button" onClick={() => setIsPasswordModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={passwordStatus.loading}>
              <Lock size={13} /> {passwordStatus.loading ? 'Updating...' : 'Update Password'}
            </Button>
          </div>
        </form>
      </Modal>

      <SaveToast show={saved} message={toastMsg} />
    </motion.div>
  )
}
