"""The application form (D-83): what a candidate fills in for one job.

Sections: personal, education, experience, compensation, links, the job's screening
questions, resume and cover letter, and the declarations (information is true; Terms and
Privacy Policy accepted). Stored encrypted with the application. None of it reaches the fit
scorer: the scorer still reads only skills, sections and years from the resume (see
matching.services.facts_to_input and the fairness tests).
"""

import json
from datetime import date
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

TERMS_VERSION = "2026-11"
NOTICE_PERIODS = {
    "immediate": "Immediate",
    "15": "15 days",
    "30": "30 days",
    "60": "60 days",
    "90": "90 days",
}
QUALIFICATIONS = ["Diploma", "Bachelor's degree", "Master's degree", "Doctorate", "Other"]
MAX_LPA = Decimal("500")


class PersonalSection(serializers.Serializer):
    full_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    phone = serializers.RegexField(
        r"^[+0-9 ()\-]{7,20}$", error_messages={"invalid": "Use digits, spaces, +, - or brackets (7-20)."}
    )
    current_city = serializers.CharField(min_length=2, max_length=80)
    willing_to_relocate = serializers.BooleanField()
    date_of_birth = serializers.DateField(required=False, allow_null=True)


class EducationSection(serializers.Serializer):
    highest_qualification = serializers.ChoiceField(choices=QUALIFICATIONS)
    college = serializers.CharField(min_length=2, max_length=160)
    branch = serializers.CharField(min_length=2, max_length=120)
    graduation_year = serializers.IntegerField(min_value=1970, max_value=date.today().year + 6)
    score_type = serializers.ChoiceField(choices=["cgpa", "percentage"])
    score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0"))
    tenth_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100")
    )
    twelfth_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100")
    )

    def validate(self, attrs):
        limit = Decimal("10") if attrs["score_type"] == "cgpa" else Decimal("100")
        if attrs["score"] > limit:
            raise serializers.ValidationError(
                {"score": f"A {attrs['score_type'].upper()} is at most {limit}."}
            )
        return attrs


class RoleRow(serializers.Serializer):
    company = serializers.CharField(min_length=2, max_length=120)
    title = serializers.CharField(min_length=2, max_length=120)
    start = serializers.RegexField(
        r"^\d{4}-(0[1-9]|1[0-2])$", error_messages={"invalid": "Use the month, like 2024-07."}
    )
    end = serializers.RegexField(
        r"^(\d{4}-(0[1-9]|1[0-2])|present)$", error_messages={"invalid": "Use the month, or present."}
    )
    responsibilities = serializers.CharField(max_length=1500, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["end"] != "present" and attrs["end"] < attrs["start"]:
            raise serializers.ValidationError({"end": "The end month cannot be before the start month."})
        return attrs


class ExperienceSection(serializers.Serializer):
    status = serializers.ChoiceField(choices=["fresher", "experienced"])
    roles = RoleRow(many=True, required=False, default=list, max_length=10)
    total_years = serializers.DecimalField(
        max_digits=4, decimal_places=1, min_value=Decimal("0"), max_value=Decimal("50")
    )

    def validate(self, attrs):
        if attrs["status"] == "experienced" and not attrs.get("roles"):
            raise serializers.ValidationError({"roles": "Add at least one role, or choose fresher."})
        if attrs["status"] == "fresher":
            attrs["roles"] = attrs.get("roles") or []
        return attrs


class CompensationSection(serializers.Serializer):
    current_ctc_lpa = serializers.DecimalField(
        max_digits=5, decimal_places=1, min_value=Decimal("0"), max_value=MAX_LPA
    )
    expected_ctc_lpa = serializers.DecimalField(
        max_digits=5, decimal_places=1, min_value=Decimal("0"), max_value=MAX_LPA
    )
    notice_period = serializers.ChoiceField(choices=list(NOTICE_PERIODS))
    earliest_joining = serializers.DateField()

    def validate_earliest_joining(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Pick today or a later date.")
        return value


class LinksSection(serializers.Serializer):
    linkedin_url = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    github_url = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    portfolio_url = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        from accounts.serializers import _https_url

        return {key: _https_url(value) for key, value in attrs.items()}


class DeclarationsSection(serializers.Serializer):
    info_true = serializers.BooleanField()
    accept_terms = serializers.BooleanField()

    def validate_info_true(self, value):
        if not value:
            raise serializers.ValidationError("Confirm that the information is true.")
        return value

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError("Accept the Terms and Conditions and the Privacy Policy.")
        return value


class ApplicationFormSerializer(serializers.Serializer):
    personal = PersonalSection()
    education = EducationSection()
    experience = ExperienceSection()
    compensation = CompensationSection()
    links = LinksSection(required=False, default=dict)
    answers = serializers.DictField(
        child=serializers.CharField(max_length=500, allow_blank=True), required=False, default=dict
    )
    use_profile_resume = serializers.BooleanField(required=False, default=False)
    cover_letter = serializers.CharField(max_length=3000, required=False, allow_blank=True, default="")
    declarations = DeclarationsSection()


def check_answers(questions: list[dict], answers: dict) -> dict:
    """Validate answers against the job's screening questions. Returns {id: cleaned answer}."""
    errors, cleaned = {}, {}
    for q in questions or []:
        raw = str(answers.get(q["id"], "")).strip()
        if not raw:
            if q.get("required", True):
                errors[q["id"]] = "Answer this question."
            continue
        if q["kind"] == "yes_no":
            if raw.lower() not in ("yes", "no"):
                errors[q["id"]] = "Answer yes or no."
                continue
            cleaned[q["id"]] = raw.lower()
        elif q["kind"] == "number":
            try:
                number = Decimal(raw)
            except ArithmeticError:
                errors[q["id"]] = "Enter a number."
                continue
            if not number.is_finite() or abs(number) > 10**6:
                errors[q["id"]] = "Enter a number."
                continue
            cleaned[q["id"]] = f"{number.normalize():f}"
        else:
            cleaned[q["id"]] = raw[:500]
    if errors:
        raise serializers.ValidationError({"answers": errors})
    return cleaned


def validate_form(raw, *, user, job) -> dict:
    """Parse and validate a submitted form (JSON text or dict). Returns plain JSON-able data.
    Identity fields come from the account, not from the form (they are locked, D-81)."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except ValueError:
            raise serializers.ValidationError(
                {"form": "The form could not be read. Reload the page and try again."}
            ) from None
    data = ApplicationFormSerializer(data=raw)
    data.is_valid(raise_exception=True)
    v = data.validated_data
    answers = check_answers(job.screening_questions, v.get("answers") or {})
    from accounts.models import Profile

    profile = Profile.objects.filter(user=user).first()  # fresh: the date of birth may have just been set
    dob = (profile.date_of_birth if profile else "") or (
        v["personal"]["date_of_birth"].isoformat() if v["personal"].get("date_of_birth") else ""
    )
    if not dob:
        raise serializers.ValidationError({"personal": {"date_of_birth": "Enter your date of birth."}})
    return json.loads(
        json.dumps(
            {
                "personal": {
                    **{k: val for k, val in v["personal"].items() if k != "date_of_birth"},
                    "full_name": user.full_name,
                    "email": user.email,
                    "date_of_birth": dob,
                },
                "education": v["education"],
                "experience": v["experience"],
                "compensation": v["compensation"],
                "links": v.get("links") or {},
                "answers": answers,
                "use_profile_resume": v["use_profile_resume"],
                "cover_letter": v["cover_letter"].strip(),
            },
            default=str,
        )
    )


def staff_view(form, *, job, blind: bool) -> dict | None:
    """What recruiters see, next to (never inside) the fit score. While screening is blind,
    identity and education stay hidden; compensation, notice and answers do not identify anyone."""
    if form is None:
        return None
    data = json.loads(form.data or "{}")
    comp = data.get("compensation", {})
    exp = data.get("experience", {})
    questions = {q["id"]: q for q in job.screening_questions or []}
    out = {
        "compensation": {
            "current_ctc_lpa": comp.get("current_ctc_lpa"),
            "expected_ctc_lpa": comp.get("expected_ctc_lpa"),
            "notice_period": NOTICE_PERIODS.get(comp.get("notice_period", ""), comp.get("notice_period")),
            "earliest_joining": comp.get("earliest_joining"),
        },
        "experience": {"status": exp.get("status"), "total_years": exp.get("total_years")},
        "willing_to_relocate": data.get("personal", {}).get("willing_to_relocate"),
        "answers": [
            {"question": questions[qid]["text"] if qid in questions else qid, "answer": answer}
            for qid, answer in (data.get("answers") or {}).items()
        ],
        "declared_at": form.declared_at.isoformat(),
        "terms_version": form.terms_version,
        "blind": blind,
    }
    if not blind:
        personal = data.get("personal", {})
        out["personal"] = {
            "phone": personal.get("phone"),
            "current_city": personal.get("current_city"),
            "date_of_birth": personal.get("date_of_birth"),
        }
        out["education"] = data.get("education")
        out["experience"]["roles"] = exp.get("roles", [])
        out["links"] = data.get("links")
        out["cover_letter"] = data.get("cover_letter", "")
    return out
