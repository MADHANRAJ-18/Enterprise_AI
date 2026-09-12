import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabaseClient'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  // ── Role & company (Module 7 prep) ───────────────────────
  const [userRole, setUserRole] = useState(null)       // 'knowledge_admin' | 'employee'
  const [companyId, setCompanyId] = useState(null)     // UUID of the user's company

  /**
   * Fetch role and company_id from the user_profiles table.
   * Called on login and on auth state change.
   */
  const fetchUserProfile = async (userId) => {
    if (!userId) {
      setUserRole(null)
      setCompanyId(null)
      return
    }
    try {
      const { data, error } = await supabase
        .from('user_profiles')
        .select('role, company_id')
        .eq('user_id', userId)
        .limit(1)
        .single()

      if (error || !data) {
        // Profile may not exist yet (e.g. trigger hasn't run) — default safely
        console.warn('[AuthContext] user_profiles not found for user', userId)
        setUserRole('employee')
        setCompanyId(null)
      } else {
        setUserRole(data.role || 'employee')
        setCompanyId(data.company_id || null)
      }
    } catch (err) {
      console.error('[AuthContext] fetchUserProfile error:', err)
      setUserRole('employee')
      setCompanyId(null)
    }
  }

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      fetchUserProfile(session?.user?.id ?? null)
      setLoading(false)
    })

    // Listen for auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        setUser(session?.user ?? null)
        fetchUserProfile(session?.user?.id ?? null)
        setLoading(false)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  const signInWithGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/dashboard`,
      },
    })
    if (error) throw error
  }

  const signInWithEmail = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })
    if (error) throw error
    return data
  }

  const signUpWithEmail = async (email, password, fullName) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { full_name: fullName, display_name: fullName },
      },
    })
    if (error) throw error
    return data
  }

  const resetPassword = async (email) => {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/update-password`,
    })
    if (error) throw error
  }

  const signOut = async () => {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }

  const getUserDisplayName = () => {
    if (!user) return ''
    return (
      user.user_metadata?.full_name ||
      user.user_metadata?.name ||
      user.email?.split('@')[0] ||
      'User'
    )
  }

  const getUserAvatar = () => {
    return user?.user_metadata?.avatar_url || user?.user_metadata?.picture || null
  }

  /** Returns true if the current user is a Knowledge Admin */
  const isKnowledgeAdmin = () => userRole === 'knowledge_admin'

  const value = {
    user,
    session,
    loading,
    // ── Role & company (Module 7 prep) ─────────────────────
    userRole,
    companyId,
    isKnowledgeAdmin,
    // ── Auth methods ───────────────────────────────────────
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    resetPassword,
    signOut,
    getUserDisplayName,
    getUserAvatar,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
