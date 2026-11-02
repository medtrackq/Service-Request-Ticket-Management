import { Navigate, Route, Routes } from 'react-router-dom'
import { AdminLayout } from './AdminLayout'
import { AuthProvider, LookupsProvider, RequireAuth } from './auth'
import { ChangePasswordPage } from './ChangePasswordPage'
import { DashboardPage } from './DashboardPage'
import { LoginPage } from './LoginPage'
import { NotificationsPage } from './NotificationsPage'
import { AssignmentRulesPage } from './pages/AssignmentRulesPage'
import { CustomersPage } from './pages/CustomersPage'
import { DepartmentsPage } from './pages/DepartmentsPage'
import { IntegrationsPage } from './pages/IntegrationsPage'
import { AuditLogsPage, NotificationLogsPage } from './pages/LogsPages'
import { RequestTypesPage } from './pages/RequestTypesPage'
import { SettingsPage } from './pages/SettingsPage'
import { UsersPage } from './pages/UsersPage'
import { WorkflowPage } from './pages/WorkflowPage'
import { ReportsPage } from './ReportsPage'
import { TicketDetailPage } from './TicketDetailPage'
import { TicketsPage } from './TicketsPage'

const adminOnly = (el: React.ReactNode) => <RequireAuth adminOnly>{el}</RequireAuth>

/** Staff / admin portal (lazy-loaded so the customer portal stays small on mobile). */
export default function AdminApp() {
  return (
    <AuthProvider>
      <LookupsProvider>
        <Routes>
          <Route path="login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <AdminLayout />
              </RequireAuth>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="change-password" element={<ChangePasswordPage />} />
            <Route path="tickets" element={<TicketsPage />} />
            <Route path="tickets/:id" element={<TicketDetailPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="users" element={adminOnly(<UsersPage />)} />
            <Route path="departments" element={adminOnly(<DepartmentsPage />)} />
            <Route path="request-types" element={adminOnly(<RequestTypesPage />)} />
            <Route path="workflow" element={adminOnly(<WorkflowPage />)} />
            <Route path="assignment-rules" element={adminOnly(<AssignmentRulesPage />)} />
            <Route path="settings" element={adminOnly(<SettingsPage />)} />
            <Route path="audit-logs" element={adminOnly(<AuditLogsPage />)} />
            <Route path="notification-logs" element={adminOnly(<NotificationLogsPage />)} />
            <Route path="integrations" element={adminOnly(<IntegrationsPage />)} />
            <Route path="customers" element={adminOnly(<CustomersPage />)} />
            <Route path="*" element={<Navigate to="/admin" replace />} />
          </Route>
        </Routes>
      </LookupsProvider>
    </AuthProvider>
  )
}
