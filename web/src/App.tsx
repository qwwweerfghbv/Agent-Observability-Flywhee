import { Navigate, Route, Routes } from 'react-router';
import AppLayout from './components/layout/AppLayout';
import ChatPage from './pages/ChatPage';
import DashboardPage from './pages/DashboardPage';
import JobsPage from './pages/JobsPage';
import ResumesPage from './pages/ResumesPage';
import ApplicationsPage from './pages/ApplicationsPage';
import SettingsPage from './pages/SettingsPage';
import ObservabilityLayout from './pages/observability/ObservabilityLayout';
import OverviewPage from './pages/observability/OverviewPage';
import MonitorPage from './pages/observability/MonitorPage';
import TracesPage from './pages/observability/TracesPage';
import QualityPage from './pages/observability/QualityPage';
import ReviewPage from './pages/observability/ReviewPage';
import ReportsPage from './pages/observability/ReportsPage';
import WeeklyPage from './pages/observability/WeeklyPage';

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<ChatPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/resumes" element={<ResumesPage />} />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        {/* 可观测平台：分组布局 + 七视图子路由（SDD §5.10.1） */}
        <Route path="/observability" element={<ObservabilityLayout />}>
          <Route index element={<OverviewPage />} />
          <Route path="monitor" element={<MonitorPage />} />
          <Route path="traces" element={<TracesPage />} />
          <Route path="quality" element={<QualityPage />} />
          <Route path="review" element={<ReviewPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="weekly" element={<WeeklyPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
