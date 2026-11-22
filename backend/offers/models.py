"""Offers: drafted by a recruiter, approved by the hiring manager then hr_admin,
sent to the candidate, accepted or declined. Offer details are encrypted at rest."""

import json
import uuid

from django.conf import settings
from django.db import models

from core.fields import EncryptedTextField


class OfferStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_APPROVAL = "pending_approval", "Pending approval"
    APPROVED = "approved", "Approved"
    SENT = "sent", "Sent to candidate"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    EXPIRED = "expired", "Expired"
    REVOKED = "revoked", "Revoked"
    REJECTED = "rejected", "Changes requested"


class ApprovalStep(models.TextChoices):
    NONE = "", "None"
    HIRING_MANAGER = "hiring_manager", "Hiring manager"
    HR_ADMIN = "hr_admin", "HR admin"


# Offers that still block a new offer for the same application.
LIVE_STATUSES = (
    OfferStatus.DRAFT,
    OfferStatus.PENDING_APPROVAL,
    OfferStatus.APPROVED,
    OfferStatus.SENT,
    OfferStatus.ACCEPTED,
    OfferStatus.REJECTED,
)
CANDIDATE_VISIBLE = (
    OfferStatus.SENT,
    OfferStatus.ACCEPTED,
    OfferStatus.DECLINED,
    OfferStatus.EXPIRED,
    OfferStatus.REVOKED,
)


class Offer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE, related_name="offers"
    )
    status = models.CharField(
        max_length=20, choices=OfferStatus.choices, default=OfferStatus.DRAFT, db_index=True
    )
    approval_step = models.CharField(max_length=20, choices=ApprovalStep.choices, blank=True, default="")
    # Designation, department, location, reporting manager, joining date and pay, as encrypted JSON.
    details = EncryptedTextField()
    expires_on = models.DateField()  # plain: needed to find expired offers
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    hm_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    hm_approved_at = models.DateTimeField(null=True, blank=True)
    hr_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    hr_approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    reject_reason = EncryptedTextField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    letter = models.ForeignKey(
        "files.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    # Acceptance acknowledgement (not a legal e-signature): typed name, time, keyed hash of the IP.
    accepted_name = EncryptedTextField(blank=True, default="")
    accept_ip_hash = models.CharField(max_length=64, blank=True, default="")
    decline_reason = EncryptedTextField(blank=True, default="")
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = EncryptedTextField(blank=True, default="")
    expired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Offer {self.id} ({self.status})"

    @property
    def data(self) -> dict:
        try:
            return json.loads(self.details or "{}")
        except ValueError:
            return {}

    @data.setter
    def data(self, value: dict) -> None:
        self.details = json.dumps(value, sort_keys=True)
