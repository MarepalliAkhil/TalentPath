"""Signed, single-use, expiring links for picking a slot from the email.

The URL carries a signed token (django.core.signing, salted) that names a
LinkToken row. Tampering fails the signature; the row enforces expiry and
single use (it is marked used when the candidate confirms a slot).
"""

from django.core import signing
from django.utils import timezone
from rest_framework.exceptions import APIException

from . import rules
from .models import LinkToken

SALT = "talentpath.interviews.schedule-link"


class InvalidLink(APIException):
    status_code = 400
    default_detail = "This scheduling link is not valid."
    default_code = "invalid_link"


class LinkGone(APIException):
    status_code = 410
    default_detail = "This scheduling link has expired or was already used. Sign in to see your interviews."
    default_code = "link_gone"


def issue(interview, now=None) -> str:
    now = now or timezone.now()
    # A fresh proposal makes older links for the same interview useless.
    LinkToken.objects.filter(interview=interview, used_at=None, expires_at__gt=now).update(expires_at=now)
    row = LinkToken.objects.create(interview=interview, expires_at=now + rules.LINK_TTL)
    return signing.dumps(str(row.id), salt=SALT)


def resolve(token: str, now=None) -> LinkToken:
    now = now or timezone.now()
    try:
        token_id = signing.loads(token, salt=SALT)
    except signing.BadSignature as exc:
        raise InvalidLink() from exc
    row = LinkToken.objects.select_related("interview").filter(id=token_id).first()
    if row is None:
        raise InvalidLink()
    if row.used_at is not None or row.expires_at <= now:
        raise LinkGone()
    return row


def use(row: LinkToken, now=None) -> None:
    updated = LinkToken.objects.filter(id=row.id, used_at=None).update(used_at=now or timezone.now())
    if not updated:
        raise LinkGone()
