from django.urls import path

from . import views

urlpatterns = [
    path("notifications", views.NotificationListView.as_view(), name="notifications"),
    path(
        "notifications/read-all",
        views.NotificationReadAllView.as_view(),
        name="notifications-read-all",
    ),
    path(
        "notifications/<uuid:pk>/read",
        views.NotificationReadView.as_view(),
        name="notification-read",
    ),
    path("realtime/ticket", views.RealtimeTicketView.as_view(), name="realtime-ticket"),
    path("outbox", views.OutboxView.as_view(), name="outbox"),
    path("demo/inbox", views.DemoInboxView.as_view(), name="demo-inbox"),
]
