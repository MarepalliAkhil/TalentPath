from notifications.models import Notification


def test_bell_lists_own_notifications_with_unread_count(client_for, application, users):
    resp = client_for("candidate").get("/api/notifications")
    assert resp.status_code == 200
    assert resp.data["unread_count"] == 1
    assert {n["title"] for n in resp.data["results"]} == {f"Application received: {application.job.title}"}


def test_mark_read_and_read_all(client_for, application, users):
    client = client_for("candidate")
    note = Notification.objects.get(user=users["candidate"])
    assert client.post(f"/api/notifications/{note.id}/read").data["read"] is True
    Notification.objects.create(user=users["candidate"], kind="x", title="Another")
    assert client.post("/api/notifications/read-all").data["updated"] == 1
    assert client.get("/api/notifications").data["unread_count"] == 0


def test_cannot_touch_someone_elses_notification(client_for, application, users):
    note = Notification.objects.get(user=users["candidate"])
    assert client_for("recruiter").post(f"/api/notifications/{note.id}/read").status_code == 404
    note.refresh_from_db()
    assert note.read_at is None
