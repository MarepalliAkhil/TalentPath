# ruff: noqa: E501  (inline e-mail HTML: table rows stay on one line each)
"""Branded HTML and plain-text email templates (D-86).

Every operation email goes through `render()`: one branded layout, with the heading, the
button label and the preference category chosen by the email's kind. Callers still write
the subject and the body text; the body is escaped before it goes into the HTML.
"""

import html
from dataclasses import dataclass

from django.conf import settings

from core.brand import get_brand


@dataclass(frozen=True)
class Template:
    category: str  # notification preference key; "account" emails cannot be switched off
    button: str  # call-to-action label


# Preference categories a person can switch off on their profile (account emails always go).
CATEGORIES = {
    "applications": "Applications and stage changes",
    "interviews": "Assignments, interviews and HR rounds",
    "offers": "Offers",
    "onboarding": "Onboarding",
    "leave": "Leave and attendance",
    "payroll": "Payslips",
    "team": "Team and hiring updates (staff)",
}

TEMPLATES: dict[str, Template] = {
    # Account
    "registration": Template("account", "Review your profile"),
    "staff_invite": Template("account", "Set your password"),
    "password_reset": Template("account", "Choose a new password"),
    "password_changed": Template("account", "Open your profile"),
    "account_updated": Template("account", "Open your profile"),
    # Applications and stages
    "application_received": Template("applications", "Track your application"),
    "application_status": Template("applications", "See your application"),
    "new_application": Template("team", "Review the application"),
    "candidate_message": Template("team", "Read the message"),
    # Assignment, interviews and the HR round (assignment and HR round arrive in prompt 2)
    "assignment_link": Template("interviews", "Start the assignment"),
    "interview_slots": Template("interviews", "Pick your interview time"),
    "interview_scheduled": Template("interviews", "See the interview"),
    "interview_link": Template("interviews", "Join the interview"),
    "interview_moved": Template("interviews", "See the new time"),
    "interview_reminder": Template("interviews", "See the interview"),
    "interview_no_show": Template("interviews", "See the interview"),
    "hr_round_link": Template("interviews", "Join the HR round"),
    "scorecard_due": Template("team", "Fill in the scorecard"),
    "hira_needs_you": Template("team", "See what needs you"),
    # Offers
    "offer_sent": Template("offers", "Read your offer"),
    "offer_accepted": Template("team", "See the offer"),
    "offer_declined": Template("team", "See the offer"),
    "offer_expired": Template("offers", "See the offer"),
    "offer_revoked": Template("offers", "See the offer"),
    "offer_approval": Template("team", "Review the offer"),
    "offer_approved": Template("team", "See the offer"),
    "offer_rejected": Template("team", "See the offer"),
    "ready_to_hire": Template("team", "Hire in one click"),
    # Onboarding
    "welcome": Template("onboarding", "Open your welcome page"),
    "onboarding_request": Template("onboarding", "Upload the documents"),
    "onboarding_complete": Template("onboarding", "Open your workspace"),
    "new_joiner": Template("team", "See the joiner"),
    "buddy_assigned": Template("onboarding", "Meet your joiner"),
    "internal_move": Template("onboarding", "See the change"),
    "internal_mobility": Template("team", "See the application"),
    # Leave, attendance and pay
    "leave_approval": Template("leave", "Review the request"),
    "leave_decided": Template("leave", "See the decision"),
    "leave_cancelled": Template("leave", "See your leave"),
    "regularisation": Template("leave", "Review the correction"),
    "attendance_missing": Template("leave", "Fix your attendance"),
    "payslip_ready": Template("payroll", "Download your payslip"),
}
DEFAULT = Template("team", "Open TalentPath")


def template_for(kind: str) -> Template:
    return TEMPLATES.get(kind, DEFAULT)


def category_for(kind: str) -> str:
    return template_for(kind).category


def _paragraphs(text: str) -> str:
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(
        f'<p style="margin:0 0 14px;line-height:1.55">{html.escape(b).replace(chr(10), "<br>")}</p>'
        for b in blocks
    )


def _split_link(body: str) -> tuple[str, str]:
    """The last line of an operation email is its link (see notify); pull it out for the button."""
    lines = body.rstrip().split("\n")
    last = lines[-1].strip() if lines else ""
    if last.startswith(("http://", "https://")) and " " not in last:
        return "\n".join(lines[:-1]).rstrip(), last
    return body.rstrip(), ""


def render(*, kind: str, subject: str, body: str) -> tuple[str, str]:
    """Return (plain text, html) for one email."""
    brand = get_brand()
    colors = brand["colors"]
    tpl = template_for(kind)
    text_body, link = _split_link(body)
    footer = (
        f"You are getting this email from {brand['name']}, a portfolio demo with fictional "
        f"companies and jobs. Change which emails you get on your profile: {settings.SITE_URL}/profile"
    )
    if tpl.category == "account":
        footer = (
            f"You are getting this account email from {brand['name']}, a portfolio demo with "
            "fictional companies and jobs. If you did not expect it, you can ignore it."
        )
    plain = text_body + (f"\n\n{tpl.button}: {link}" if link else "") + f"\n\n--\n{footer}\n"
    button = (
        f'<p style="margin:22px 0"><a href="{html.escape(link, quote=True)}" '
        f'style="background:{colors["primary"]};color:#ffffff;text-decoration:none;'
        f'padding:12px 20px;border-radius:10px;font-weight:600;display:inline-block">'
        f"{html.escape(tpl.button)}</a></p>"
        f'<p style="margin:0 0 14px;font-size:13px;color:{colors["muted"]}">Or paste this link: '
        f"{html.escape(link)}</p>"
        if link
        else ""
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(subject)}</title></head>
<body style="margin:0;background:{colors["canvas"]};font-family:Segoe UI,Arial,sans-serif;color:{colors["ink"]}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:16px">
<tr><td style="padding:20px 28px;border-bottom:1px solid {colors["canvasDeep"]}">
<strong style="font-size:18px;color:{colors["primaryStrong"]}">{html.escape(brand["name"])}</strong>
<span style="font-size:13px;color:{colors["muted"]}"> · {html.escape(brand["tagline"])}</span></td></tr>
<tr><td style="padding:24px 28px">
<h1 style="font-size:20px;margin:0 0 16px">{html.escape(subject)}</h1>
{_paragraphs(text_body)}{button}
</td></tr>
<tr><td style="padding:16px 28px;border-top:1px solid {colors["canvasDeep"]};font-size:12px;color:{colors["muted"]}">
{html.escape(footer)}</td></tr>
</table></td></tr></table></body></html>"""
    return plain, page
