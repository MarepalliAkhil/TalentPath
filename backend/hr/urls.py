from django.urls import path

from . import views

urlpatterns = [
    path("offers/<uuid:pk>/hire", views.HireView.as_view(), name="offer-hire"),
    path("onboarding/me", views.MyOnboardingView.as_view(), name="onboarding-me"),
    path("onboarding", views.OnboardingListView.as_view(), name="onboarding-list"),
    path("onboarding/<uuid:pk>", views.OnboardingDetailView.as_view(), name="onboarding-detail"),
    path(
        "onboarding/tasks/<uuid:pk>/complete",
        views.TaskCompleteView.as_view(),
        name="onboarding-task-complete",
    ),
    path("onboarding/tasks/<uuid:pk>/reopen", views.TaskReopenView.as_view(), name="onboarding-task-reopen"),
    path(
        "onboarding/tasks/<uuid:pk>/document",
        views.TaskDocumentView.as_view(),
        name="onboarding-task-document",
    ),
    path("leave/balances", views.LeaveBalancesView.as_view(), name="leave-balances"),
    path("leave/preview", views.LeavePreviewView.as_view(), name="leave-preview"),
    path("leave/requests", views.LeaveRequestsView.as_view(), name="leave-requests"),
    path("leave/requests/<uuid:pk>", views.LeaveDetailView.as_view(), name="leave-detail"),
    path("leave/requests/<uuid:pk>/document", views.LeaveDocumentView.as_view(), name="leave-document"),
    path("leave/requests/<uuid:pk>/cancel", views.LeaveCancelView.as_view(), name="leave-cancel"),
    path(
        "leave/requests/<uuid:pk>/approve",
        views.LeaveDecisionView.as_view(decision="approve"),
        name="leave-approve",
    ),
    path(
        "leave/requests/<uuid:pk>/reject",
        views.LeaveDecisionView.as_view(decision="reject"),
        name="leave-reject",
    ),
    path("leave/approvals", views.ApprovalsView.as_view(), name="leave-approvals"),
    path("leave/adjust", views.LeaveAdjustView.as_view(), name="leave-adjust"),
    path("team-calendar", views.TeamCalendarView.as_view(), name="team-calendar"),
    path("hr/policies", views.PoliciesView.as_view(), name="hr-policies"),
    path("hr/attention", views.AttentionView.as_view(), name="hr-attention"),
    path("hr/config", views.ConfigView.as_view(), name="hr-config"),
    path("hr/config/leave-types", views.ConfigLeaveTypesView.as_view(), name="hr-config-leave-types"),
    path("hr/config/leave-types/<uuid:pk>", views.ConfigLeaveTypeView.as_view(), name="hr-config-leave-type"),
    path("hr/config/holidays", views.ConfigHolidaysView.as_view(), name="hr-config-holidays"),
    path("hr/config/holidays/<uuid:pk>", views.ConfigHolidayView.as_view(), name="hr-config-holiday"),
    path(
        "hr/config/work-policy/<uuid:pk>", views.ConfigWorkPolicyView.as_view(), name="hr-config-work-policy"
    ),
    path("attendance/me", views.AttendanceMeView.as_view(), name="attendance-me"),
    path("attendance/check-in", views.CheckInView.as_view(), name="attendance-check-in"),
    path("attendance/check-out", views.CheckOutView.as_view(), name="attendance-check-out"),
    path(
        "attendance/regularisations", views.RegularisationsView.as_view(), name="attendance-regularisations"
    ),
    path(
        "attendance/regularisations/<uuid:pk>/decide",
        views.RegularisationDecideView.as_view(),
        name="attendance-regularisation-decide",
    ),
    path("attendance/team", views.AttendanceTeamView.as_view(), name="attendance-team"),
]
