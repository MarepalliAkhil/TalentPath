from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.utils import paginate
from core.views import PolicyAPIView

from .models import EmailOutbox, Notification
from .services import issue_ws_ticket


def notification_dict(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "read": n.read_at is not None,
        "created_at": n.created_at.isoformat(),
    }


def email_dict(e: EmailOutbox) -> dict:
    return {
        "id": str(e.id),
        "to_email": e.to_email,
        "kind": e.kind,
        "subject": e.subject,
        "body": e.body,
        "created_at": e.created_at.isoformat(),
    }


class NotificationListView(PolicyAPIView):
    policy_action = "notifications.list"

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)
        if request.query_params.get("unread") == "1":
            qs = qs.filter(read_at__isnull=True)
        response = paginate(self, request, qs, notification_dict)
        response.data["unread_count"] = Notification.objects.filter(
            user=request.user, read_at__isnull=True
        ).count()
        return response


class NotificationReadView(PolicyAPIView):
    policy_action = "notifications.read"

    def post(self, request, pk):
        note = get_object_or_404(Notification, pk=pk, user=request.user)
        if note.read_at is None:
            note.read_at = timezone.now()
            note.save(update_fields=["read_at"])
        return Response(notification_dict(note))


class NotificationReadAllView(PolicyAPIView):
    policy_action = "notifications.read_all"

    def post(self, request):
        updated = Notification.objects.filter(user=request.user, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return Response({"updated": updated})


class RealtimeTicketView(PolicyAPIView):
    policy_action = "realtime.ticket"

    def post(self, request):
        return Response(
            {"ticket": issue_ws_ticket(request.user), "expires_in": settings.WS_TICKET_TTL_SECONDS}
        )


class OutboxView(PolicyAPIView):
    policy_action = "outbox.list"

    def get(self, request):
        qs = EmailOutbox.objects.all()
        to = request.query_params.get("to", "").strip()
        if to:
            qs = qs.filter(to_email__iexact=to)
        return paginate(self, request, qs, email_dict)


class DemoInboxView(PolicyAPIView):
    """Lets visitors of the demo read simulated emails sent to *.example addresses."""

    policy_action = "demo.inbox"
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "demo_inbox"

    def get(self, request):
        email = request.query_params.get("email", "").strip().lower()
        if not settings.DEMO_MODE or not email.endswith(".example"):
            raise Http404
        emails = EmailOutbox.objects.filter(to_email__iexact=email)[:10]
        return Response({"results": [email_dict(e) for e in emails]})
