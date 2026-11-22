from django.urls import path

from . import views

urlpatterns = [
    path("jobs/<uuid:pk>/interview-plan", views.InterviewPlanView.as_view(), name="interview-plan"),
    path("interviewers", views.InterviewerListView.as_view(), name="interviewers"),
    path("interviewers/<uuid:pk>", views.InterviewerUpdateView.as_view(), name="interviewer-update"),
    path("availability", views.AvailabilityView.as_view(), name="availability"),
    path("availability/blocks", views.BlockedTimeView.as_view(), name="availability-blocks"),
    path("availability/blocks/<uuid:pk>", views.BlockedTimeDetailView.as_view(), name="availability-block"),
    path("my/interviews", views.MyInterviewsView.as_view(), name="my-interviews"),
    path("interviews/assigned", views.AssignedInterviewsView.as_view(), name="interviews-assigned"),
    path(
        "applications/<uuid:pk>/interviews",
        views.ApplicationInterviewsView.as_view(),
        name="application-interviews",
    ),
    path("applications/<uuid:pk>/interviews/propose", views.ProposeView.as_view(), name="interviews-propose"),
    path(
        "applications/<uuid:pk>/interviews/manual",
        views.ManualScheduleView.as_view(),
        name="interviews-manual",
    ),
    path("interviews/<uuid:pk>/hold", views.HoldView.as_view(), name="interview-hold"),
    path("interviews/<uuid:pk>/confirm", views.ConfirmView.as_view(), name="interview-confirm"),
    path("interviews/<uuid:pk>/reschedule", views.RescheduleView.as_view(), name="interview-reschedule"),
    path("interviews/<uuid:pk>/decline", views.DeclineView.as_view(), name="interview-decline"),
    path("interviews/<uuid:pk>/no-show", views.NoShowView.as_view(), name="interview-no-show"),
    path("interviews/<uuid:pk>/calendar.ics", views.CalendarView.as_view(), name="interview-calendar"),
    path("interviews/<uuid:pk>/scorecards", views.ScorecardView.as_view(), name="interview-scorecards"),
    path("schedule/<str:token>", views.ScheduleLinkView.as_view(), name="schedule-link"),
    path("schedule/<str:token>/<str:action>", views.ScheduleLinkView.as_view(), name="schedule-link-action"),
]
