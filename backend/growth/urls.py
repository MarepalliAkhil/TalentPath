from django.urls import path

from . import views

urlpatterns = [
    path("career/profile", views.CareerProfileView.as_view(), name="career-profile"),
    path("career/map", views.CareerMapView.as_view(), name="career-map"),
    path("career/map/<uuid:pk>", views.CareerJobMapView.as_view(), name="career-job-map"),
    path("career/next-role", views.NextRoleView.as_view(), name="career-next-role"),
    path("internal/jobs", views.InternalJobsView.as_view(), name="internal-jobs"),
    path("internal/jobs/<uuid:pk>/apply", views.InternalApplyView.as_view(), name="internal-apply"),
]
