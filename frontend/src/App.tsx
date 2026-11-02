import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import { OverviewPage } from './pages/OverviewPage'
import { RepositoriesPage } from './pages/RepositoriesPage'
import { ChatPage } from './pages/ChatPage'
import { SecurityPage } from './pages/SecurityPage'
import { GraphPage } from './pages/GraphPage'
import { SettingsPage } from './pages/SettingsPage'
import { ChatSelectorPage } from './pages/ChatSelectorPage'
import { SecuritySelectorPage } from './pages/SecuritySelectorPage'

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="repositories" element={<RepositoriesPage />} />
        <Route path="repositories/:repositoryId" element={<ChatPage />} />
        <Route path="chat" element={<ChatSelectorPage />} />
        <Route path="chat/:repositoryId" element={<ChatPage />} />
        <Route path="security" element={<SecuritySelectorPage />} />
        <Route path="security/:repositoryId" element={<SecurityPage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="settings" element={<SettingsPage />} />
        {/* Redirect legacy /chat and /security without params to selector pages */}
        <Route path="chat" element={<Navigate to="/chat" replace />} />
        <Route path="security" element={<Navigate to="/security" replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return <AppRoutes />
}