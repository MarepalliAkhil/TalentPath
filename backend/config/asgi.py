"""ASGI entry point: HTTP through Django, WebSockets through Channels.

Vercel cannot proxy WebSockets, so the browser connects straight to the
backend host with a single-use ticket (see notifications.consumers).
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import OriginValidator  # noqa: E402
from django.conf import settings  # noqa: E402

from notifications.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidator(URLRouter(websocket_urlpatterns), settings.WS_ALLOWED_ORIGINS),
    }
)
