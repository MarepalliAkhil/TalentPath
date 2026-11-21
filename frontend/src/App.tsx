import type { ReactElement } from 'react';
import { Route, Routes } from 'react-router-dom';
import { RequireRole } from '@/auth/RequireRole';
import { AppShell } from '@/components/AppShell';
import { PublicLayout } from '@/components/PublicLayout';
import { AuditPage } from '@/pages/admin/AuditPage';
import { OrgAdminPage } from '@/pages/admin/OrgAdminPage';
import { OutboxPage } from '@/pages/admin/OutboxPage';
import { StaffAdminPage } from '@/pages/admin/StaffAdminPage';
import { ApplyPage } from '@/pages/candidate/ApplyPage';
import { CandidateDashboard } from '@/pages/candidate/CandidateDashboard';
import { DemoInboxPage } from '@/pages/public/DemoInboxPage';
import { ForgotPasswordPage } from '@/pages/public/ForgotPasswordPage';
import { HomePage } from '@/pages/public/HomePage';
import { JobDetailPage } from '@/pages/public/JobDetailPage';
import { JobsPage } from '@/pages/public/JobsPage';
import { LoginPage } from '@/pages/public/LoginPage';
import { NotFoundPage } from '@/pages/public/NotFoundPage';
import { RegisterPage } from '@/pages/public/RegisterPage';
import { ResetPasswordPage } from '@/pages/public/ResetPasswordPage';
import { NotificationsPage } from '@/pages/shared/NotificationsPage';
import { ProfilePage } from '@/pages/shared/ProfilePage';
import { EmployeeDashboard } from '@/pages/staff/EmployeeDashboard';
import { JobApplicationsPage } from '@/pages/staff/JobApplicationsPage';
import { JobFormPage } from '@/pages/staff/JobFormPage';
import { JobsManagePage } from '@/pages/staff/JobsManagePage';
import { StaffOverview } from '@/pages/staff/StaffOverview';

/** Every protected element is wrapped in RequireRole with its key from shared/policy.json. */
const guard = (route: string, element: ReactElement) => <RequireRole route={route}>{element}</RequireRole>;

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<HomePage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/:slug" element={<JobDetailPage />} />
        <Route path="jobs/:slug/apply" element={guard('/jobs/:slug/apply', <ApplyPage />)} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="forgot-password" element={<ForgotPasswordPage />} />
        <Route path="reset-password" element={<ResetPasswordPage />} />
        <Route path="demo-inbox" element={<DemoInboxPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route element={<AppShell />}>
        <Route path="candidate" element={guard('/candidate', <CandidateDashboard />)} />
        <Route path="recruiter" element={guard('/recruiter', <StaffOverview role="recruiter" />)} />
        <Route path="recruiter/jobs" element={guard('/recruiter/jobs', <JobsManagePage scope="mine" />)} />
        <Route path="recruiter/jobs/new" element={guard('/recruiter/jobs/new', <JobFormPage />)} />
        <Route path="recruiter/jobs/:id/edit" element={guard('/recruiter/jobs/:id/edit', <JobFormPage />)} />
        <Route path="recruiter/jobs/:id/applications" element={guard('/recruiter/jobs/:id/applications', <JobApplicationsPage />)} />
        <Route path="manager" element={guard('/manager', <StaffOverview role="hiring_manager" />)} />
        <Route path="employee" element={guard('/employee', <EmployeeDashboard />)} />
        <Route path="admin" element={guard('/admin', <StaffOverview role="hr_admin" />)} />
        <Route path="admin/jobs" element={guard('/admin/jobs', <JobsManagePage scope="all" />)} />
        <Route path="admin/staff" element={guard('/admin/staff', <StaffAdminPage />)} />
        <Route path="admin/org" element={guard('/admin/org', <OrgAdminPage />)} />
        <Route path="admin/audit" element={guard('/admin/audit', <AuditPage />)} />
        <Route path="admin/outbox" element={guard('/admin/outbox', <OutboxPage />)} />
        <Route path="profile" element={guard('/profile', <ProfilePage />)} />
        <Route path="notifications" element={guard('/notifications', <NotificationsPage />)} />
      </Route>
    </Routes>
  );
}
