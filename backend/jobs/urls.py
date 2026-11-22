from django.urls import path

from applications.views import BulkStatusView, JobApplicationsView, JobBoardView

from . import views

urlpatterns = [
    path("public/jobs", views.CareerJobListView.as_view(), name="career-jobs"),
    path("public/jobs/<slug:slug>", views.CareerJobDetailView.as_view(), name="career-job"),
    path("jobs", views.StaffJobListView.as_view(), name="jobs"),
    path("jobs/<uuid:pk>", views.StaffJobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:pk>/status", views.StaffJobStatusView.as_view(), name="job-status"),
    path("jobs/<uuid:pk>/applications", JobApplicationsView.as_view(), name="job-applications"),
    path("jobs/<uuid:pk>/board", JobBoardView.as_view(), name="job-board"),
    path("jobs/<uuid:pk>/applications/bulk-status", BulkStatusView.as_view(), name="job-bulk-status"),
]
