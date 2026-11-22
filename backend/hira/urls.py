from django.urls import path

from . import views

urlpatterns = [
    path("hira/ask", views.AskView.as_view(), name="hira-ask"),
    path("hira/message", views.MessageRecruiterView.as_view(), name="hira-message"),
    path("hira/briefing", views.BriefingView.as_view(), name="hira-briefing"),
    path("hira/activity", views.ActivityListView.as_view(), name="hira-activity"),
    path("hira/activity/summary", views.ActivitySummaryView.as_view(), name="hira-activity-summary"),
]
