from django.urls import path

from . import views

urlpatterns = [
    path("analytics/<str:report>", views.AnalyticsView.as_view(), name="analytics"),
    path(
        "analytics/<str:report>/<str:key>.csv", views.AnalyticsExportView.as_view(), name="analytics-export"
    ),
]
