"""Listens to `offers.events.offer_accepted`: tells HR the hire is ready (one click on the offer)."""

from django.dispatch import receiver

from offers.events import offer_accepted


@receiver(offer_accepted, dispatch_uid="hr-offer-accepted")
def ready_to_hire(sender, offer, **kwargs):
    from accounts.models import Role, User
    from notifications.services import notify

    job = offer.application.job
    for admin in User.objects.filter(role=Role.HR_ADMIN, is_active=True):
        notify(
            admin,
            kind="ready_to_hire",
            title=f"Ready to hire: {offer.application.candidate.full_name} for {job.title}",
            body="The offer was accepted. Choose Hire on the offer to create the employee record "
            "and onboarding.",
            link=f"/offers/{offer.id}",
            email=False,
        )
