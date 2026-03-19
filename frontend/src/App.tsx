import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import SourcesPage from './pages/SourcesPage'
import TasksPage from './pages/TasksPage'
import RecordsPage from './pages/RecordsPage'
import SchedulesPage from './pages/SchedulesPage'
import NotificationsPage from './pages/NotificationsPage'
import WorkersPage from './pages/WorkersPage'
import AgentsPage from './pages/AgentsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="sources" element={<SourcesPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="records" element={<RecordsPage />} />
          <Route path="schedules" element={<SchedulesPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="workers" element={<WorkersPage />} />
          <Route path="agents" element={<AgentsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
