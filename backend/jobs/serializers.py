import re
from decimal import Decimal

from rest_framework import serializers

from accounts.models import Role, User
from org.models import Company, Skill

from .models import Job
from .seo import seo_block


class JobWriteSerializer(serializers.ModelSerializer):
    required_skills = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Skill.objects.all(), required=False
    )
    nice_to_have_skills = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Skill.objects.all(), required=False
    )
    hiring_manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=Role.MANAGER, is_active=True),
        required=False,
        allow_null=True,
    )
    openings = serializers.IntegerField(min_value=1, max_value=500, required=False)
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), required=False, allow_null=True
    )
    ctc_min_lpa = serializers.DecimalField(
        max_digits=5, decimal_places=1, min_value=Decimal("0"), required=False, allow_null=True
    )
    ctc_max_lpa = serializers.DecimalField(
        max_digits=5, decimal_places=1, min_value=Decimal("0"), required=False, allow_null=True
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "department",
            "location",
            "level",
            "work_mode",
            "employment_type",
            "description",
            "required_skills",
            "nice_to_have_skills",
            "openings",
            "hiring_manager",
            "blind_screening",
            "reveal_stage",
            "audience",
            "company",
            "about_team",
            "responsibilities",
            "required_qualifications",
            "preferred_qualifications",
            "benefits",
            "ctc_min_lpa",
            "ctc_max_lpa",
            "screening_questions",
        ]

    def _texts(self, value, limit=15):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise serializers.ValidationError("Give a list of short texts.")
        value = [" ".join(v.split()) for v in value if v.strip()]
        if len(value) > limit or any(len(v) > 300 for v in value):
            raise serializers.ValidationError(f"Use at most {limit} items of up to 300 characters.")
        return value

    def validate_responsibilities(self, value):
        return self._texts(value)

    def validate_required_qualifications(self, value):
        return self._texts(value)

    def validate_preferred_qualifications(self, value):
        return self._texts(value)

    def validate_benefits(self, value):
        return self._texts(value)

    def validate_screening_questions(self, value):
        return clean_screening_questions(value)

    def validate_title(self, value):
        value = " ".join(value.split())
        if len(value) < 3:
            raise serializers.ValidationError("Title is too short.")
        return value

    def validate_description(self, value):
        value = value.strip()
        if len(value) < 30:
            raise serializers.ValidationError("Describe the role in at least 30 characters.")
        return value

    def validate(self, attrs):
        required = attrs.get("required_skills")
        nice = attrs.get("nice_to_have_skills")
        if self.instance is not None:
            if required is None:
                required = list(self.instance.required_skills.all())
            if nice is None:
                nice = list(self.instance.nice_to_have_skills.all())
        overlap = {s.pk for s in required or []} & {s.pk for s in nice or []}
        if overlap:
            raise serializers.ValidationError(
                {"nice_to_have_skills": "A skill cannot be both required and nice to have."}
            )
        if len(required or []) > 15 or len(nice or []) > 15:
            raise serializers.ValidationError("Use at most 15 skills per list.")
        low = attrs.get("ctc_min_lpa", getattr(self.instance, "ctc_min_lpa", None))
        high = attrs.get("ctc_max_lpa", getattr(self.instance, "ctc_max_lpa", None))
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError(
                {"ctc_max_lpa": "The top of the range must be at least the bottom."}
            )
        return attrs


QUESTION_KINDS = {"yes_no": "Yes or no", "number": "Number", "text": "Short text"}


def clean_screening_questions(value) -> list[dict]:
    """Recruiter-defined screening questions per job (D-83): up to 10, three kinds."""
    if not isinstance(value, list):
        raise serializers.ValidationError("Give a list of questions.")
    if len(value) > 10:
        raise serializers.ValidationError("Use at most 10 screening questions.")
    out, used = [], set()
    for n, item in enumerate(value, 1):
        if not isinstance(item, dict):
            raise serializers.ValidationError("Each question needs text and a kind.")
        text = " ".join(str(item.get("text", "")).split())
        kind = str(item.get("kind", ""))
        if not 5 <= len(text) <= 200:
            raise serializers.ValidationError(f"Question {n}: write 5 to 200 characters.")
        if kind not in QUESTION_KINDS:
            raise serializers.ValidationError(f"Question {n}: the kind must be yes/no, number or short text.")
        qid = str(item.get("id") or "")
        if not re.fullmatch(r"q[0-9]{1,3}", qid) or qid in used:
            qid = next(f"q{i}" for i in range(1, 100) if f"q{i}" not in used)
        used.add(qid)
        out.append({"id": qid, "text": text, "kind": kind, "required": bool(item.get("required", True))})
    return out


def company_dict(company, detail: bool = False) -> dict | None:
    if company is None:
        return None
    data = {
        "id": str(company.id),
        "name": company.name,
        "slug": company.slug,
        "industry": company.industry,
        "headquarters": company.headquarters,
        "logo_initials": company.logo_initials,
        "logo_color": company.logo_color,
    }
    if detail:
        data.update(
            {
                "tagline": company.tagline,
                "about": company.about,
                "size": company.size,
                "founded": company.founded,
                "offices": company.offices,
                "culture": company.culture,
                "benefits": company.benefits,
                "hiring_process": company.hiring_process,
                "website": company.website,
            }
        )
    return data


def ctc_range(job) -> dict | None:
    if job.ctc_min_lpa is None and job.ctc_max_lpa is None:
        return None
    low, high = job.ctc_min_lpa, job.ctc_max_lpa
    fmt = lambda v: f"{v.normalize():f}" if v is not None else None  # noqa: E731
    label = (
        f"₹{fmt(low)}–{fmt(high)} LPA" if low is not None and high is not None else f"₹{fmt(low or high)} LPA"
    )
    return {
        "min_lpa": float(low) if low is not None else None,
        "max_lpa": float(high) if high is not None else None,
        "label": label,
    }


def page_sections(job) -> dict:
    """The long job page (D-85). Benefits and hiring steps fall back to the company's."""
    company = job.company
    return {
        "about_team": job.about_team,
        "responsibilities": job.responsibilities,
        "required_qualifications": job.required_qualifications,
        "preferred_qualifications": job.preferred_qualifications,
        "benefits": job.benefits or (company.benefits if company else []),
        "hiring_process": (company.hiring_process if company and company.hiring_process else DEFAULT_PROCESS),
        "ctc": ctc_range(job),
    }


DEFAULT_PROCESS = [
    {"step": "Shortlist", "detail": "A recruiter reviews your application, usually within a week."},
    {"step": "Assignment", "detail": "A short online assignment, sent by email, done at your own time."},
    {"step": "Technical interview", "detail": "A video interview with the team, booked at a time you pick."},
    {"step": "HR round", "detail": "A conversation about the role, expectations and joining."},
    {"step": "Offer", "detail": "A written offer you accept online."},
    {"step": "Onboarding", "detail": "Documents, a buddy and a first-week plan before day one."},
]


def _ref(obj, **extra):
    return None if obj is None else {"id": str(obj.pk), "name": str(obj), **extra}


def skill_list(qs):
    return [{"id": str(s.id), "name": s.name, "slug": s.slug} for s in qs]


def staff_job_dict(job: Job) -> dict:
    return {
        "id": str(job.id),
        "slug": job.slug,
        "title": job.title,
        "department": _ref(job.department),
        "location": _ref(job.location),
        "level": _ref(job.level),
        "work_mode": job.work_mode,
        "work_mode_label": job.get_work_mode_display(),
        "employment_type": job.employment_type,
        "description": job.description,
        "required_skills": skill_list(job.required_skills.all()),
        "nice_to_have_skills": skill_list(job.nice_to_have_skills.all()),
        "openings": job.openings,
        "blind_screening": job.blind_screening,
        "reveal_stage": job.reveal_stage,
        "audience": job.audience,
        "audience_label": job.get_audience_display(),
        "company": company_dict(job.company),
        "about_team": job.about_team,
        "responsibilities": job.responsibilities,
        "required_qualifications": job.required_qualifications,
        "preferred_qualifications": job.preferred_qualifications,
        "benefits": job.benefits,
        "ctc_min_lpa": float(job.ctc_min_lpa) if job.ctc_min_lpa is not None else None,
        "ctc_max_lpa": float(job.ctc_max_lpa) if job.ctc_max_lpa is not None else None,
        "screening_questions": job.screening_questions,
        "status": job.status,
        "status_label": job.get_status_display(),
        "created_by": {"id": str(job.created_by_id), "name": job.created_by.full_name},
        "hiring_manager": (
            {"id": str(job.hiring_manager_id), "name": job.hiring_manager.full_name}
            if job.hiring_manager_id
            else None
        ),
        "application_count": getattr(job, "application_count", None),
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "published_at": job.published_at.isoformat() if job.published_at else None,
    }


def public_job_dict(job: Job, detail: bool = False) -> dict:
    data = {
        "slug": job.slug,
        "title": job.title,
        "department": {"name": job.department.name, "slug": job.department.slug},
        "location": {
            "name": job.location.name,
            "slug": job.location.slug,
            "country": job.location.country,
        },
        "level": job.level.name,
        "work_mode": job.work_mode,
        "work_mode_label": job.get_work_mode_display(),
        "employment_type": job.employment_type,
        "employment_type_label": job.get_employment_type_display(),
        "openings": job.openings,
        "published_at": job.published_at.isoformat() if job.published_at else None,
        "required_skills": skill_list(job.required_skills.all()),
        "nice_to_have_skills": skill_list(job.nice_to_have_skills.all()),
        "excerpt": " ".join(job.description.split())[:180],
        "company": company_dict(job.company),
        "ctc": ctc_range(job),
    }
    if detail:
        data["description"] = job.description
        data["company"] = company_dict(job.company, detail=True)
        data.update(page_sections(job))
        data["screening_question_count"] = len(job.screening_questions or [])
        data["seo"] = seo_block(job)
    return data
