"""Service events other parts of the product can subscribe to.

`offer_accepted` is sent after a candidate accepts. Week 3B's onboarding listens
to it (hr.signals) and tells the recruiter the hire is ready; the hire itself
is one click by the recruiter or hr_admin (POST /api/offers/<id>/hire).
"""

from django.dispatch import Signal

# Sent with offer=<Offer> after a candidate accepts and the change is saved.
offer_accepted = Signal()
