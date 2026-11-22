from django.urls import include, path

from core.views import RobotsView, SitemapView

urlpatterns = [
    path("sitemap.xml", SitemapView.as_view(), name="sitemap"),
    path("robots.txt", RobotsView.as_view(), name="robots"),
    path("api/", include("core.urls")),
    path("api/auth/", include("accounts.urls_auth")),
    path("api/", include("accounts.urls")),
    path("api/", include("org.urls")),
    path("api/", include("jobs.urls")),
    path("api/", include("applications.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("hira.urls")),
    path("api/", include("matching.urls")),
    path("api/", include("interviews.urls")),
    path("api/", include("offers.urls")),
    path("api/", include("hr.urls")),
]
