import type { ReactElement } from 'react';
import { Route, Routes } from 'react-router-dom';
import { RequireRole } from '@/auth/RequireRole';
import { AppShell } from '@/components/AppShell';
import { PublicLayout } from '@/components/PublicLayout';
import { AuditPage } from '@/pages/admin/AuditPage';
import { FairnessPage } from '@/pages/admin/FairnessPage';
import { OrgAdminPage } from '@/pages/admin/OrgAdminPage';
import { OutboxPage } from '@/pages/admin/OutboxPage';
import { StaffAdminPage } from '@/pages/admin/StaffAdminPage';
import { ApplyPage } from '@/pages/candidate/ApplyPage';
import { CandidateDashboard } from '@/pages/candidate/CandidateDashboard';
import { CandidateOfferPage } from '@/pages/candidate/CandidateOfferPage';
import { AnalyticsPage } from '@/pages/growth/AnalyticsPage';
import { CareerJobPage } from '@/pages/growth/CareerJobPage';
import { CareerPage } from '@/pages/growth/CareerPage';
import { InternalJobsPage } from '@/pages/growth/InternalJobsPage';
import { HiraActivityPage } from '@/pages/hira/HiraActivityPage';
import { ApprovalsPage } from '@/pages/hr/ApprovalsPage';
import { AttendancePage } from '@/pages/hr/AttendancePage';
import { HrSettingsPage } from '@/pages/hr/HrSettingsPage';
import { LeavePage } from '@/pages/hr/LeavePage';
import { OnboardingDetailPage } from '@/pages/hr/OnboardingDetailPage';
import { OnboardingPage } from '@/pages/hr/OnboardingPage';
import { PoliciesPage } from '@/pages/hr/PoliciesPage';
import { TeamCalendarPage } from '@/pages/hr/TeamCalendarPage';
import { WelcomePage } from '@/pages/hr/WelcomePage';
import { AvailabilityPage } from '@/pages/interviews/AvailabilityPage';
import { MyInterviewsPage } from '@/pages/interviews/MyInterviewsPage';
import { ScorecardPage } from '@/pages/interviews/ScorecardPage';
import { OfferDetailPage } from '@/pages/offers/OfferDetailPage';
import { OffersPage } from '@/pages/offers/OffersPage';
import { DemoInboxPage } from '@/pages/public/DemoInboxPage';
import { ForRecruitersPage } from '@/pages/public/ForRecruitersPage';
import { ForgotPasswordPage } from '@/pages/public/ForgotPasswordPage';
import { HomePage } from '@/pages/public/HomePage';
import { JobDetailPage } from '@/pages/public/JobDetailPage';
import { JobsPage } from '@/pages/public/JobsPage';
import { LoginPage } from '@/pages/public/LoginPage';
import { NotFoundPage } from '@/pages/public/NotFoundPage';
import { RegisterPage } from '@/pages/public/RegisterPage';
import { ResetPasswordPage } from '@/pages/public/ResetPasswordPage';
import { ScheduleLinkPage } from '@/pages/public/ScheduleLinkPage';
import { NotificationsPage } from '@/pages/shared/NotificationsPage';
import { ProfilePage } from '@/pages/shared/ProfilePage';
import { EmployeeDashboard } from '@/pages/staff/EmployeeDashboard';
import { InterviewPlanPage } from '@/pages/staff/InterviewPlanPage';
import { JobApplicationsPage } from '@/pages/staff/JobApplicationsPage';
import { JobFormPage } from '@/pages/staff/JobFormPage';
import { JobsManagePage } from '@/pages/staff/JobsManagePage';
import { PipelineBoardPage } from '@/pages/staff/PipelineBoardPage';
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
        <Route path="schedule/:token" element={<ScheduleLinkPage />} />
        <Route path="for-recruiters" element={<ForRecruitersPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route element={<AppShell />}>
        <Route path="candidate" element={guard('/candidate', <CandidateDashboard />)} />
        <Route path="candidate/offers/:id" element={guard('/candidate/offers/:id', <CandidateOfferPage />)} />
        <Route path="recruiter" element={guard('/recruiter', <StaffOverview role="recruiter" />)} />
        <Route path="recruiter/jobs" element={guard('/recruiter/jobs', <JobsManagePage scope="mine" />)} />
        <Route path="recruiter/jobs/new" element={guard('/recruiter/jobs/new', <JobFormPage />)} />
        <Route path="recruiter/jobs/:id/edit" element={guard('/recruiter/jobs/:id/edit', <JobFormPage />)} />
        <Route path="recruiter/jobs/:id/applications" element={guard('/recruiter/jobs/:id/applications', <JobApplicationsPage />)} />
        <Route path="recruiter/jobs/:id/board" element={guard('/recruiter/jobs/:id/board', <PipelineBoardPage />)} />
        <Route path="recruiter/jobs/:id/interview-plan" element={guard('/recruiter/jobs/:id/interview-plan', <InterviewPlanPage />)} />
        <Route path="hira" element={guard('/hira', <HiraActivityPage />)} />
        <Route path="interviews" element={guard('/interviews', <MyInterviewsPage />)} />
        <Route path="interviews/availability" element={guard('/interviews/availability', <AvailabilityPage />)} />
        <Route path="interviews/:id/scorecard" element={guard('/interviews/:id/scorecard', <ScorecardPage />)} />
        <Route path="offers" element={guard('/offers', <OffersPage />)} />
        <Route path="offers/:id" element={guard('/offers/:id', <OfferDetailPage />)} />
        <Route path="career" element={guard('/career', <CareerPage />)} />
        <Route path="career/jobs/:id" element={guard('/career/jobs/:id', <CareerJobPage />)} />
        <Route path="internal-jobs" element={guard('/internal-jobs', <InternalJobsPage />)} />
        <Route path="analytics" element={guard('/analytics', <AnalyticsPage />)} />
        <Route path="welcome" element={guard('/welcome', <WelcomePage />)} />
        <Route path="onboarding" element={guard('/onboarding', <OnboardingPage />)} />
        <Route path="onboarding/:id" element={guard('/onboarding/:id', <OnboardingDetailPage />)} />
        <Route path="leave" element={guard('/leave', <LeavePage />)} />
        <Route path="leave/approvals" element={guard('/leave/approvals', <ApprovalsPage />)} />
        <Route path="team-calendar" element={guard('/team-calendar', <TeamCalendarPage />)} />
        <Route path="attendance" element={guard('/attendance', <AttendancePage />)} />
        <Route path="hr/policies" element={guard('/hr/policies', <PoliciesPage />)} />
        <Route path="admin/hr-settings" element={guard('/admin/hr-settings', <HrSettingsPage />)} />
        <Route path="manager" element={guard('/manager', <StaffOverview role="hiring_manager" />)} />
        <Route path="employee" element={guard('/employee', <EmployeeDashboard />)} />
        <Route path="admin" element={guard('/admin', <StaffOverview role="hr_admin" />)} />
        <Route path="admin/jobs" element={guard('/admin/jobs', <JobsManagePage scope="all" />)} />
        <Route path="admin/staff" element={guard('/admin/staff', <StaffAdminPage />)} />
        <Route path="admin/org" element={guard('/admin/org', <OrgAdminPage />)} />
        <Route path="admin/audit" element={guard('/admin/audit', <AuditPage />)} />
        <Route path="admin/outbox" element={guard('/admin/outbox', <OutboxPage />)} />
        <Route path="admin/fairness" element={guard('/admin/fairness', <FairnessPage />)} />
        <Route path="profile" element={guard('/profile', <ProfilePage />)} />
        <Route path="notifications" element={guard('/notifications', <NotificationsPage />)} />
      </Route>
    </Routes>
  );
}
