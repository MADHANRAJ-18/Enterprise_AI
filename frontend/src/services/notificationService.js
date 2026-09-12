/**
 * notificationService.js
 * ─────────────────────────────────────────────────────────────
 * Service for in-app notifications and user preferences in Supabase.
 * Respects RLS and real-time subscription channels.
 * ─────────────────────────────────────────────────────────────
 */

import { supabase } from '../lib/supabaseClient'

/**
 * Fetch notifications for an authenticated user.
 */
export async function fetchNotifications(userId, { limit = 50, offset = 0, unreadOnly = false } = {}) {
  if (!userId) return { data: [], unreadCount: 0, error: null }

  try {
    let query = supabase
      .from('notifications')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })
      .range(offset, offset + limit - 1)

    if (unreadOnly) {
      query = query.eq('is_read', false)
    }

    const { data, error } = await query
    if (error) throw error

    // Count unread
    const { count, error: countErr } = await supabase
      .from('notifications')
      .select('*', { count: 'exact', head: true })
      .eq('user_id', userId)
      .eq('is_read', false)

    return {
      data: data || [],
      unreadCount: countErr ? 0 : (count || 0),
      error: null,
    }
  } catch (err) {
    console.error('[notificationService] fetchNotifications error:', err)
    return { data: [], unreadCount: 0, error: err.message || err }
  }
}

/**
 * Mark a single notification as read.
 */
export async function markNotificationAsRead(userId, notificationId) {
  if (!userId || !notificationId) return { success: false }

  try {
    const { error } = await supabase
      .from('notifications')
      .update({ is_read: true })
      .eq('id', notificationId)
      .eq('user_id', userId)

    if (error) throw error
    return { success: true }
  } catch (err) {
    console.error('[notificationService] markNotificationAsRead error:', err)
    return { success: false, error: err.message || err }
  }
}

/**
 * Mark all notifications as read for an authenticated user.
 */
export async function markAllNotificationsAsRead(userId) {
  if (!userId) return { success: false }

  try {
    const { error } = await supabase
      .from('notifications')
      .update({ is_read: true })
      .eq('user_id', userId)
      .eq('is_read', false)

    if (error) throw error
    return { success: true }
  } catch (err) {
    console.error('[notificationService] markAllNotificationsAsRead error:', err)
    return { success: false, error: err.message || err }
  }
}

/**
 * Fetch notification preferences for an authenticated user.
 * Defaults to company_file_updates = true if no row exists yet.
 */
export async function fetchUserPreferences(userId) {
  if (!userId) return { company_file_updates: true, error: null }

  try {
    const { data, error } = await supabase
      .from('user_preferences')
      .select('user_id, company_file_updates, updated_at')
      .eq('user_id', userId)
      .maybeSingle()

    if (error && error.code !== 'PGRST116') {
      throw error
    }

    if (!data) {
      return { company_file_updates: true, error: null }
    }

    return {
      company_file_updates: data.company_file_updates !== false,
      updated_at: data.updated_at,
      error: null,
    }
  } catch (err) {
    console.error('[notificationService] fetchUserPreferences error:', err)
    return { company_file_updates: true, error: err.message || err }
  }
}

/**
 * Update user notification preferences.
 */
export async function updateUserPreferences(userId, { company_file_updates }) {
  if (!userId) return { success: false, error: 'User not authenticated' }

  try {
    const payload = {
      user_id: userId,
      company_file_updates: Boolean(company_file_updates),
      updated_at: new Date().toISOString(),
    }

    const { data, error } = await supabase
      .from('user_preferences')
      .upsert(payload, { onConflict: 'user_id' })
      .select()
      .single()

    if (error) throw error
    return { success: true, data }
  } catch (err) {
    console.error('[notificationService] updateUserPreferences error:', err)
    return { success: false, error: err.message || err }
  }
}

/**
 * Subscribe to realtime notifications for an authenticated user.
 */
export function subscribeToNotifications(userId, onNotificationChange) {
  if (!userId || typeof onNotificationChange !== 'function') {
    return () => {}
  }

  const channel = supabase
    .channel(`user-notifications:${userId}`)
    .on(
      'postgres_changes',
      {
        event: '*',
        schema: 'public',
        table: 'notifications',
        filter: `user_id=eq.${userId}`,
      },
      (payload) => {
        onNotificationChange(payload)
      }
    )
    .subscribe()

  return () => {
    supabase.removeChannel(channel)
  }
}
