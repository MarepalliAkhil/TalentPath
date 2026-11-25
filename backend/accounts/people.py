"""Profiles and admin user management (prompt 1: D-80, D-81, D-82).

- A person edits their own details; identity fields are locked (email, full legal name,
  date of birth once set, employee ID, role, joining date).
- Only an admin changes a locked field, always with a reason, always audited.
- The admin creates staff (with an invite email), assigns roles and reporting managers,
  deactivates people (never deletes anyone with history) and cannot open candidates'
  documents (no policy action gives the admin role access to resumes or applications).
"""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from core.audit import audit

from .models import Profile, Role, User
from .prefill import dumps, loads
from .services import revoke_sessions, set_phone

PHOTO_MAX_BYTES = 2 * 1024 * 1024
PHOTO_TYPES = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"RIFF": "image/webp",  # checked further below (WEBP at offset 8)
}


def photo_type(data: bytes) -> str:
    """Content type from the file's first bytes; '' when it is not a PNG, JPEG or WebP image."""
    for magic, ctype in PHOTO_TYPES.items():
        if data.startswith(magic):
            if ctype == "image/webp" and data[8:12] != b"WEBP":
                return ""
            return ctype
    return ""


def employee_of(user):
    from hr.models import Employee

    return (
        Employee.objects.select_related("manager__user", "company", "department", "location")
        .filter(user=user)
        .first()
    )


def employee_dict(emp) -> dict | None:
    if emp is None:
        return None
    return {
        "id": str(emp.id),
        "code": emp.code,
        "designation": emp.designation,
        "department": emp.department.name,
        "location": emp.location.name,
        "joined_on": emp.joined_on.isoformat(),
        "manager": {"id": str(emp.manager_id), "name": emp.manager.user.full_name}
        if emp.manager_id
        else None,
        "company": {"id": str(emp.company_id), "name": emp.company.name} if emp.company_id else None,
    }


def profile_dict(user: User) -> dict:
    from growth.models import ResumeVersion
    from notifications.templates import CATEGORIES

    from .serializers import user_dict

    profile, _ = Profile.objects.get_or_create(user=user)
    emp = employee_of(user)
    prefs = profile.notification_prefs or {}
    versions = ResumeVersion.objects.filter(user=user)[:10]
    return {
        **user_dict(user),
        "headline": profile.headline,
        "location_text": profile.location_text,
        "phone": profile.phone,
        "address": profile.address,
        "linkedin_url": profile.linkedin_url,
        "github_url": profile.github_url,
        "portfolio_url": profile.portfolio_url,
        "skills": profile.skills or [],
        "education": loads(profile.education),
        "experience": loads(profile.experience),
        "date_of_birth": profile.date_of_birth or None,
        "has_photo": profile.photo_id is not None,
        "employee": employee_dict(emp),
        # Identity fields the person cannot change; an admin can, with an audited reason.
        "locked": {
            "email": True,
            "full_name": True,
            "role": True,
            "date_of_birth": bool(profile.date_of_birth),
            "employee_code": emp is not None,
            "joined_on": emp is not None,
        },
        "notification_prefs": {key: prefs.get(key, True) is not False for key in CATEGORIES},
        "notification_categories": [{"key": k, "label": v} for k, v in CATEGORIES.items()],
        "resume_versions": [
            {
                "id": str(v.id),
                "filename": v.filename,
                "uploaded_at": v.uploaded_at.isoformat(),
                "current": v.is_current,
            }
            for v in versions
        ],
    }


def update_own_profile(request, data: dict) -> Profile:
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    if "date_of_birth" in data:
        if profile.date_of_birth:
            raise ValidationError(
                {"date_of_birth": "Your date of birth is locked. Ask an admin to correct it."}
            )
        profile.date_of_birth = data["date_of_birth"].isoformat()
    for field in ("headline", "location_text", "address", "linkedin_url", "github_url", "portfolio_url"):
        if field in data:
            setattr(profile, field, data[field].strip())
    if "phone" in data:
        set_phone(profile, data["phone"])
    if "skills" in data:
        profile.skills = data["skills"]
    if "education" in data:
        profile.education = dumps(data["education"])
    if "experience" in data:
        profile.experience = dumps(data["experience"])
    profile.save()
    audit(request, "profile.update", target=profile, fields=sorted(data.keys()))
    return profile


# ---------------------------------------------------------------- admin
def _resolve(model, pk, field: str):
    if pk is None:
        return None
    obj = model.objects.filter(pk=pk).first()
    if obj is None:
        raise ValidationError({field: "Not found."})
    return obj


def _check_manager(employee, manager) -> None:
    if manager is None:
        return
    if employee is not None and manager.pk == employee.pk:
        raise ValidationError({"manager": "A person cannot report to themselves."})
    if not manager.user.is_active:
        raise ValidationError({"manager": "Choose an active manager."})
    walker, seen = manager, set()
    while walker is not None and walker.pk not in seen:
        if employee is not None and walker.pk == employee.pk:
            raise ValidationError({"manager": "That would make a reporting loop."})
        seen.add(walker.pk)
        walker = walker.manager


@transaction.atomic
def create_staff(request, v: dict) -> User:
    from hr.models import Employee
    from hr.onboarding import next_code
    from org.models import Company, Department, Location

    from .services import create_user, send_staff_invite

    user = create_user(email=v["email"], full_name=v["full_name"], role=v["role"])
    details = v.get("employee")
    if details:
        manager = _resolve(Employee, details.get("manager"), "manager")
        _check_manager(None, manager)
        Employee.objects.create(
            user=user,
            code=next_code(),
            designation=details["designation"],
            department=_resolve(Department, details["department"], "department"),
            location=_resolve(Location, details["location"], "location"),
            joined_on=details["joined_on"],
            manager=manager,
            company=_resolve(Company, details.get("company"), "company"),
        )
    send_staff_invite(user, invited_by=request.user)
    audit(request, "users.create", target=user, role=user.role, employee=bool(details))
    return user


@transaction.atomic
def admin_update(request, user: User, v: dict) -> list[str]:
    """Apply an admin's change. Returns the changed field names (values are never audited)."""
    from hr.models import Employee
    from org.models import Company

    if user == request.user and (v.get("is_active") is False or ("role" in v and v["role"] != user.role)):
        raise ValidationError({"detail": "You cannot deactivate or change the role of your own account."})
    if user.role == Role.ADMIN and "role" in v:
        raise ValidationError({"role": "Admin accounts are created with the bootstrap_admin command only."})
    if user.role == Role.CANDIDATE and "role" in v:
        raise ValidationError(
            {"role": "Candidates become employees through an offer and the one-click hire."}
        )
    changed: list[str] = []
    profile, _ = Profile.objects.get_or_create(user=user)
    emp = Employee.objects.filter(user=user).first()

    if "email" in v:
        email = v["email"].strip().lower()
        if email != user.email:
            if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                raise ValidationError({"email": "An account with this email already exists."})
            user.email = email
            changed.append("email")
    for field in ("full_name", "role", "is_active"):
        if field in v and getattr(user, field) != v[field]:
            setattr(user, field, v[field].strip() if field == "full_name" else v[field])
            changed.append(field)
    if changed:
        user.save(update_fields=list(changed))
    if "date_of_birth" in v:
        new = v["date_of_birth"].isoformat() if v["date_of_birth"] else ""
        if new != profile.date_of_birth:
            profile.date_of_birth = new
            profile.save(update_fields=["date_of_birth", "updated_at"])
            changed.append("date_of_birth")

    emp_fields = [f for f in ("employee_code", "joined_on", "manager", "company") if f in v]
    if emp_fields and emp is None:
        raise ValidationError({emp_fields[0]: "This person has no employee record."})
    if emp is not None:
        if "employee_code" in v and v["employee_code"] != emp.code:
            if Employee.objects.filter(code=v["employee_code"]).exclude(pk=emp.pk).exists():
                raise ValidationError({"employee_code": "Another employee already has this ID."})
            emp.code = v["employee_code"]
            changed.append("employee_code")
        if "joined_on" in v and v["joined_on"] != emp.joined_on:
            emp.joined_on = v["joined_on"]
            changed.append("joined_on")
        if "manager" in v:
            manager = _resolve(Employee, v["manager"], "manager")
            _check_manager(emp, manager)
            if (manager.pk if manager else None) != emp.manager_id:
                emp.manager = manager
                changed.append("manager")
        if "company" in v:
            company = _resolve(Company, v["company"], "company")
            if (company.pk if company else None) != emp.company_id:
                emp.company = company
                changed.append("company")
        emp.save()

    if changed:
        if {"role", "is_active", "email"} & set(changed):
            revoke_sessions(user)
        action = (
            "users.override"
            if set(changed) & {"email", "full_name", "date_of_birth", "role", "employee_code", "joined_on"}
            else "users.update"
        )
        audit(request, action, target=user, fields=changed, reason=v.get("reason", "").strip())
        _tell_user(user, changed)
    return changed


def _tell_user(user: User, changed: list[str]) -> None:
    from notifications.services import notify

    labels = {
        "email": "email address",
        "full_name": "name",
        "date_of_birth": "date of birth",
        "role": "role",
        "employee_code": "employee ID",
        "joined_on": "joining date",
        "manager": "reporting manager",
        "company": "company",
        "is_active": "account status",
    }
    words = ", ".join(labels[c] for c in changed if c in labels)
    if not words or not user.is_active:
        return
    notify(
        user,
        kind="account_updated",
        title="An admin updated your account",
        body=f"An admin changed your {words}. If this looks wrong, reply to your HR team.",
        link="/profile",
    )
