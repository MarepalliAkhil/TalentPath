from django.urls import path

from .views import AuditListView, NightlyView, PingView, TickView

urlpatterns = [
    path("ping", PingView.as_view(), name="ping"),
    path("internal/tick", TickView.as_view(), name="internal-tick"),
    path("audit", AuditListView.as_view(), name="audit"),
    path("internal/nightly", NightlyView.as_view(), name="internal-nightly"),
]
