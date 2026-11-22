from django.urls import path

from . import views

urlpatterns = [
    path("applications", views.ApplicationListCreateView.as_view(), name="applications"),
    path("applications/<uuid:pk>", views.ApplicationDetailView.as_view(), name="application-detail"),
    path(
        "applications/<uuid:pk>/withdraw",
        views.ApplicationWithdrawView.as_view(),
        name="application-withdraw",
    ),
    path(
        "applications/<uuid:pk>/status",
        views.ApplicationStatusView.as_view(),
        name="application-status",
    ),
    path("applications/<uuid:pk>/reveal", views.RevealView.as_view(), name="application-reveal"),
    path("applications/<uuid:pk>/notes", views.NotesView.as_view(), name="application-notes"),
    path(
        "applications/<uuid:pk>/resume",
        views.ResumeDownloadView.as_view(),
        name="application-resume",
    ),
    path("dashboard/summary", views.DashboardSummaryView.as_view(), name="dashboard-summary"),
]
