import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mail, Lock, User, Eye, EyeOff, Chrome, ArrowRight, Bot, Zap, Shield, Cpu } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.4, ease: [0.4, 0, 0.2, 1] },
  }),
}

function ForgotPasswordView({ onBack }) {
  const { resetPassword } = useAuth()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await resetPassword(email)
      setSent(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div initial="hidden" animate="visible" variants={fadeUp} className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-surface-900">Reset Password</h2>
        <p className="text-sm text-surface-500 mt-1">Enter your email to receive a reset link.</p>
      </div>
      {sent ? (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 text-sm text-emerald-700">
          ✅ Reset email sent! Check your inbox.
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Email Address"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
            error={error}
            prefix={<Mail size={15} />}
          />
          <Button type="submit" loading={loading} className="w-full">
            Send Reset Link
          </Button>
        </form>
      )}
      <button onClick={onBack} className="text-sm text-primary-600 hover:text-primary-700 font-medium transition-colors">
        ← Back to login
      </button>
    </motion.div>
  )
}

function LoginForm({ onForgot }) {
  const { signInWithEmail, signInWithGoogle } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await signInWithEmail(email, password)
    } catch (err) {
      setError(err.message || 'Invalid email or password')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogle = async () => {
    setGoogleLoading(true)
    try {
      await signInWithGoogle()
    } catch (err) {
      setError(err.message)
      setGoogleLoading(false)
    }
  }

  return (
    <motion.div initial="hidden" animate="visible" className="space-y-5">
      <motion.div variants={fadeUp} custom={0}>
        <h2 className="text-2xl font-bold text-surface-900">Welcome back</h2>
        <p className="text-sm text-surface-500 mt-1">Sign in to your workspace</p>
      </motion.div>

      {/* Google SSO */}
      <motion.div variants={fadeUp} custom={1} className="flex justify-center">
        <button
          id="google-signin-btn"
          onClick={handleGoogle}
          disabled={googleLoading}
          className="inline-flex items-center gap-2.5 px-5 py-2 rounded-full border border-surface-200 bg-surface-100 hover:bg-surface-200 text-sm font-medium text-surface-700 transition-all duration-150 active:scale-[0.98] disabled:opacity-60 shadow-sm"
        >
          {googleLoading ? (
            <div className="w-3.5 h-3.5 border-2 border-surface-300 border-t-primary-600 rounded-full animate-spin" />
          ) : (
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
          )}
          Sign in with Google
        </button>
      </motion.div>

      <motion.div variants={fadeUp} custom={2} className="flex items-center gap-3">
        <div className="flex-1 h-px bg-surface-200" />
        <span className="text-xs text-surface-400 font-medium">or continue with email</span>
        <div className="flex-1 h-px bg-surface-200" />
      </motion.div>

      <form onSubmit={handleLogin} className="space-y-4">
        <motion.div variants={fadeUp} custom={3}>
          <Input
            label="Email Address"
            type="email"
            id="login-email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
            prefix={<Mail size={15} />}
          />
        </motion.div>
        <motion.div variants={fadeUp} custom={4}>
          <Input
            label="Password"
            type={showPw ? 'text' : 'password'}
            id="login-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            prefix={<Lock size={15} />}
            suffix={
              <button type="button" onClick={() => setShowPw((p) => !p)} className="cursor-pointer">
                {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            }
          />
        </motion.div>

        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="text-sm text-red-600 bg-red-50 border border-red-200 px-3 py-2 rounded-lg"
          >
            {error}
          </motion.div>
        )}

        <motion.div variants={fadeUp} custom={5} className="flex justify-end">
          <button
            type="button"
            onClick={onForgot}
            className="text-sm text-primary-600 hover:text-primary-700 font-medium transition-colors"
          >
            Forgot password?
          </button>
        </motion.div>

        <motion.div variants={fadeUp} custom={6}>
          <Button type="submit" loading={loading} className="w-full" size="lg">
            Sign in <ArrowRight size={16} />
          </Button>
        </motion.div>
      </form>
    </motion.div>
  )
}

function SignUpForm() {
  const { signUpWithEmail } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  const handleSignUp = async (e) => {
    e.preventDefault()
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    setError('')
    try {
      await signUpWithEmail(email, password, name)
      setSuccess(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <motion.div initial="hidden" animate="visible" variants={fadeUp} className="text-center py-8 space-y-4">
        <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto">
          <svg className="w-8 h-8 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h3 className="text-xl font-bold text-surface-900">Check your email!</h3>
        <p className="text-sm text-surface-500">We sent a confirmation link to <strong>{email}</strong>. Click it to activate your account.</p>
      </motion.div>
    )
  }

  return (
    <motion.div initial="hidden" animate="visible" className="space-y-5">
      <motion.div variants={fadeUp} custom={0}>
        <h2 className="text-2xl font-bold text-surface-900">Create account</h2>
        <p className="text-sm text-surface-500 mt-1">Join your enterprise workspace</p>
      </motion.div>

      <form onSubmit={handleSignUp} className="space-y-4">
        <motion.div variants={fadeUp} custom={1}>
          <Input
            label="Full Name"
            type="text"
            id="signup-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="John Doe"
            required
            prefix={<User size={15} />}
          />
        </motion.div>
        <motion.div variants={fadeUp} custom={2}>
          <Input
            label="Work Email"
            type="email"
            id="signup-email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
            prefix={<Mail size={15} />}
          />
        </motion.div>
        <motion.div variants={fadeUp} custom={3}>
          <Input
            label="Password"
            type={showPw ? 'text' : 'password'}
            id="signup-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Min. 8 characters"
            required
            prefix={<Lock size={15} />}
            suffix={
              <button type="button" onClick={() => setShowPw((p) => !p)} className="cursor-pointer">
                {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            }
          />
        </motion.div>
        <motion.div variants={fadeUp} custom={4}>
          <Input
            label="Confirm Password"
            type={showPw ? 'text' : 'password'}
            id="signup-confirm"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Repeat password"
            required
            prefix={<Lock size={15} />}
          />
        </motion.div>

        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="text-sm text-red-600 bg-red-50 border border-red-200 px-3 py-2 rounded-lg"
          >
            {error}
          </motion.div>
        )}

        <motion.div variants={fadeUp} custom={5}>
          <Button type="submit" loading={loading} className="w-full" size="lg">
            Create Account <ArrowRight size={16} />
          </Button>
        </motion.div>
      </form>
    </motion.div>
  )
}

const features = [
  { icon: Bot, label: 'Enterprise-Powered AI', desc: 'Advanced AI reasoning' },
  { icon: Shield, label: 'Enterprise Security', desc: 'SOC 2 Type II compliant' },
  { icon: Cpu, label: 'RAG Pipeline', desc: 'Intelligent document retrieval' },
  { icon: Zap, label: 'Real-time Insights', desc: 'Instant knowledge access' },
]

export function AuthPage() {
  const [tab, setTab] = useState('login')
  const [showForgot, setShowForgot] = useState(false)

  return (
    <div className="min-h-screen flex">
      {/* Left branding panel */}
      <div className="hidden lg:flex flex-col justify-between w-[480px] flex-shrink-0 bg-gradient-to-br from-primary-900 via-primary-800 to-primary-950 px-12 py-10 relative overflow-hidden">
        {/* Decorative circles */}
        <div className="absolute -top-32 -left-32 w-80 h-80 rounded-full bg-white/5" />
        <div className="absolute -bottom-20 -right-20 w-64 h-64 rounded-full bg-white/5" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full bg-white/3" />

        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
              <Bot size={20} className="text-white" />
            </div>
            <div>
              <span className="text-white font-bold text-lg">Enterprise AI</span>
              <p className="text-primary-300 text-xs">Knowledge Assistant</p>
            </div>
          </div>
        </div>

        <div className="relative space-y-8">
          <div>
            <h1 className="text-4xl font-bold text-white leading-tight">
              Intelligent knowledge,<br />
              <span className="text-primary-300">amplified by AI</span>
            </h1>
            <p className="text-primary-200 mt-4 text-base leading-relaxed">
              Harness the power of multi-agent AI to analyze documents, extract insights, and supercharge your team's productivity.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {features.map(({ icon: Icon, label, desc }) => (
              <div key={label} className="flex items-start gap-3 bg-white/10 backdrop-blur rounded-xl p-3.5">
                <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center flex-shrink-0">
                  <Icon size={15} className="text-white" />
                </div>
                <div>
                  <p className="text-white text-xs font-semibold">{label}</p>
                  <p className="text-primary-300 text-[11px] mt-0.5">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-primary-400 text-xs">
          © 2024 Enterprise AI Assistant. All rights reserved.
        </p>
      </div>

      {/* Right auth panel */}
      <div className="flex-1 flex items-center justify-center p-6 bg-surface-50">
        <div className="w-full max-w-[420px]">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="w-8 h-8 rounded-xl bg-primary-600 flex items-center justify-center">
              <Bot size={16} className="text-white" />
            </div>
            <span className="font-bold text-surface-900">Enterprise AI</span>
          </div>

          <div className="bg-surface-100 rounded-2xl shadow-card border border-surface-200/60 p-8">
            <AnimatePresence mode="wait">
              {showForgot ? (
                <motion.div key="forgot" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                  <ForgotPasswordView onBack={() => setShowForgot(false)} />
                </motion.div>
              ) : (
                <motion.div key="auth" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                  {/* Tabs */}
                  <div className="flex bg-surface-100 rounded-xl p-1 mb-6">
                    {['login', 'signup'].map((t) => (
                      <button
                        key={t}
                        id={`auth-tab-${t}`}
                        onClick={() => setTab(t)}
                        className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all duration-150 ${
                          tab === t
                            ? 'bg-surface-50 text-surface-900 shadow-sm'
                            : 'text-surface-500 hover:text-surface-700'
                        }`}
                      >
                        {t === 'login' ? 'Sign In' : 'Sign Up'}
                      </button>
                    ))}
                  </div>

                  <AnimatePresence mode="wait">
                    {tab === 'login' ? (
                      <motion.div key="login" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <LoginForm onForgot={() => setShowForgot(true)} />
                      </motion.div>
                    ) : (
                      <motion.div key="signup" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <SignUpForm />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {!showForgot && (
            <p className="text-center text-xs text-surface-400 mt-4">
              By continuing, you agree to our{' '}
              <a href="#" className="text-primary-600 hover:underline">Terms</a> and{' '}
              <a href="#" className="text-primary-600 hover:underline">Privacy Policy</a>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
