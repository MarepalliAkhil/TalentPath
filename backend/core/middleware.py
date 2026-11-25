"""Health checks from the hosting platform may arrive with a Host header Django does not allow
(Render has been seen to send `localhost:10000`). Instead of allowing every host, this middleware
answers GET /api/ping itself, with no database query, only when the host is not allowed. Every other
path, and ping with a normal host, goes through the usual host validation."""

from django.core.exceptions import DisallowedHost
from django.http import JsonResponse

HEALTH_PATH = "/api/ping"


class HealthCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH and request.method in ("GET", "HEAD"):
            try:
                request.get_host()
            except DisallowedHost:
                response = JsonResponse({"status": "ok"})
                response["Cache-Control"] = "no-store"
                return response
        return self.get_response(request)
