import { Routes, Route, Navigate } from 'react-router-dom'
import { PrivateRoute, PublicRoute } from './RouteGuards'
import { AppLayout } from '../components/layout/AppLayout'
import { AuthPage } from '../pages/Auth/AuthPage'
import { DashboardPage } from '../pages/Dashboard/DashboardPage'
import { ChatPage } from '../pages/Chat/ChatPage'
import { DocumentsPage } from '../pages/Documents/DocumentsPage'
import { HistoryPage } from '../pages/History/HistoryPage'
import { ProfilePage } from '../pages/Profile/ProfilePage'
import { SettingsPage } from '../pages/Settings/SettingsPage'

export function AppRouter() {
  return (
    <Routes>
      {/* Public routes */}
      <Route element={<PublicRoute />}>
        <Route path="/login" element={<AuthPage />} />
      </Route>

      {/* Protected routes */}
      <Route element={<PrivateRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>

      {/* Fallback */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
