import { useState } from 'react'
import { motion } from 'framer-motion'
import { User, Mail, Lock, Camera, Shield, CheckCircle, Chrome, Eye, EyeOff, ExternalLink } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { supabase } from '../../lib/supabaseClient'
import { Card, CardHeader, CardBody, CardFooter } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Avatar } from '../../components/ui/Avatar'
import { Badge } from '../../components/ui/Badge'

function SaveToast({ show }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.9 }}
      animate={show ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 16, scale: 0.9 }}
      className="fixed bottom-6 right-6 flex items-center gap-2 bg-emerald-600 text-white px-4 py-2.5 rounded-xl shadow-lg z-50 text-sm font-medium"
    >
      <CheckCircle size={16} /> Changes saved!
    </motion.div>
  )
}

export function ProfilePage() {
  const { user, getUserDisplayName, getUserAvatar } = useAuth()
  const [displayName, setDisplayName] = useState(getUserDisplayName())
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [pwLoading, setPwLoading] = useState(false)
  const [saved, setSaved] = useState(false)
  const [pwError, setPwError] = useState('')

  const isGoogleUser =
    user?.app_metadata?.provider === 'google' ||
    user?.app_metadata?.providers?.includes('google') ||
    user?.identities?.some((id) => id.provider === 'google') ||
    Boolean(user?.user_metadata?.avatar_url && !user?.app_metadata?.provider)

  const hasGoogle = isGoogleUser || Boolean(user?.user_metadata?.avatar_url)

  const handleSaveProfile = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const { error } = await supabase.auth.updateUser({
        data: { full_name: displayName, display_name: displayName }
      })
      if (error) console.warn('[ProfilePage] profile metadata update:', error)
    } catch (err) {
      console.warn('[ProfilePage] update error:', err)
    }
    setLoading(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const handleChangePassword = async (e) => {
    e.preventDefault()
    setPwError('')
    if (newPw !== confirmPw) { setPwError('Passwords do not match'); return }
    if (newPw.length < 8) { setPwError('Password must be at least 8 characters'); return }
    setPwLoading(true)
    try {
      const { error } = await supabase.auth.updateUser({ password: newPw })
      if (error) throw error
      setCurrentPw(''); setNewPw(''); setConfirmPw('')
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setPwError(err.message || 'Failed to update password')
    } finally {
      setPwLoading(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="p-6 max-w-3xl mx-auto space-y-6"
    >
      <div>
        <h1 className="text-2xl font-bold text-surface-900">Profile</h1>
        <p className="text-sm text-surface-500 mt-0.5">Manage your personal information and account security</p>
      </div>

      {/* Avatar + basic info */}
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-surface-900">Personal Information</h2>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleSaveProfile} className="space-y-6">
            {/* Avatar */}
            <div className="flex items-center gap-5">
              <div className="relative">
                <Avatar src={getUserAvatar()} name={getUserDisplayName()} size="2xl" />
                <button
                  type="button"
                  className="absolute bottom-0 right-0 w-8 h-8 rounded-full bg-primary-600 text-white flex items-center justify-center hover:bg-primary-700 transition-colors shadow-md"
                >
                  <Camera size={14} />
                </button>
              </div>
              <div>
                <p className="text-sm font-semibold text-surface-900">{getUserDisplayName()}</p>
                <p className="text-xs text-surface-500 mt-0.5">{user?.email}</p>
                <p className="text-xs text-surface-400 mt-1">Click the camera icon to upload a new photo</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Display Name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                prefix={<User size={15} />}
                placeholder="Your name"
              />
              <Input
                label="Email Address"
                type="email"
                value={user?.email || ''}
                readOnly
                prefix={<Mail size={15} />}
                className="bg-surface-50 cursor-not-allowed"
              />
            </div>

            <div className="flex justify-end">
              <Button type="submit" loading={loading}>Save Changes</Button>
            </div>
          </form>
        </CardBody>
      </Card>

      {/* Change password / Account Security */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Lock size={15} className="text-surface-400" />
            <h2 className="text-sm font-semibold text-surface-900">
              {isGoogleUser ? 'Account Security' : 'Change Password'}
            </h2>
          </div>
        </CardHeader>
        <CardBody>
          {isGoogleUser ? (
            <div className="p-4 rounded-xl bg-surface-50 border border-surface-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3.5">
                <div className="w-10 h-10 rounded-xl bg-white border border-surface-200 flex items-center justify-center flex-shrink-0 shadow-sm">
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-surface-900">Managed by Google</p>
                    <Badge variant="green" size="sm"><CheckCircle size={10} /> Active</Badge>
                  </div>
                  <p className="text-xs text-surface-500 mt-1 leading-relaxed">
                    You signed in with Google (<span className="text-surface-700 font-medium">{user?.email}</span>). 
                    Your account security and password management are handled securely by Google Sign-In, so you do not need a separate password.
                  </p>
                </div>
              </div>
              <a
                href="https://myaccount.google.com/security"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium bg-white text-surface-700 hover:text-surface-900 hover:bg-surface-100 border border-surface-300 shadow-sm transition-colors flex-shrink-0"
              >
                <ExternalLink size={13} />
                Manage Google Account
              </a>
            </div>
          ) : (
            <form onSubmit={handleChangePassword} className="space-y-4">
              <Input
                label="Current Password"
                type={showPw ? 'text' : 'password'}
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                placeholder="Enter current password"
                prefix={<Lock size={15} />}
                suffix={
                  <button type="button" onClick={() => setShowPw((p) => !p)} className="cursor-pointer">
                    {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                }
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="New Password"
                  type={showPw ? 'text' : 'password'}
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  placeholder="Min. 8 characters"
                  prefix={<Lock size={15} />}
                />
                <Input
                  label="Confirm New Password"
                  type={showPw ? 'text' : 'password'}
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  placeholder="Repeat new password"
                  prefix={<Lock size={15} />}
                  error={pwError}
                />
              </div>
              <div className="flex justify-end">
                <Button type="submit" loading={pwLoading} variant="secondary">Update Password</Button>
              </div>
            </form>
          )}
        </CardBody>
      </Card>

      {/* Connected accounts */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Shield size={15} className="text-surface-400" />
            <h2 className="text-sm font-semibold text-surface-900">Connected Accounts</h2>
          </div>
        </CardHeader>
        <CardBody>
          <div className="flex items-center justify-between p-3 bg-surface-50 rounded-xl">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-surface-100 border border-surface-200 flex items-center justify-center shadow-sm">
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-surface-900">Google Account</p>
                <p className="text-xs text-surface-400">{hasGoogle ? user?.email : 'Not connected'}</p>
              </div>
            </div>
            {hasGoogle ? (
              <Badge variant="green"><CheckCircle size={10} /> Connected</Badge>
            ) : (
              <Button variant="secondary" size="sm">Connect</Button>
            )}
          </div>
        </CardBody>
      </Card>

      {/* Danger zone */}
      <Card className="border-red-200">
        <CardHeader className="border-b-red-100">
          <h2 className="text-sm font-semibold text-red-700">Danger Zone</h2>
        </CardHeader>
        <CardBody>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-surface-900">Delete Account</p>
              <p className="text-xs text-surface-500 mt-0.5">Permanently delete your account and all data. This cannot be undone.</p>
            </div>
            <Button variant="danger" size="sm">Delete Account</Button>
          </div>
        </CardBody>
      </Card>

      <SaveToast show={saved} />
    </motion.div>
  )
}
