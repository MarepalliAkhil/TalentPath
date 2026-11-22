from django.urls import path

from . import views

ACTIONS = ["submit", "approve", "reject", "send", "revoke", "accept", "decline"]

urlpatterns = [
    path("offers", views.OfferListView.as_view(), name="offers"),
    path("my/offers", views.MyOffersView.as_view(), name="my-offers"),
    path(
        "applications/<uuid:pk>/offers", views.ApplicationOfferCreateView.as_view(), name="application-offers"
    ),
    path("offers/<uuid:pk>", views.OfferDetailView.as_view(), name="offer-detail"),
    path("offers/<uuid:pk>/letter", views.OfferLetterView.as_view(), name="offer-letter"),
    *[
        path(
            f"offers/<uuid:pk>/{name}", views.OfferActionView.as_view(action_name=name), name=f"offer-{name}"
        )
        for name in ACTIONS
    ],
]
