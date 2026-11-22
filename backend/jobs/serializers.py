from rest_framework import serializers

from accounts.models import Role, User
from org.models import Skill

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
        queryset=User.objects.filter(role=Role.HIRING_MANAGER, is_active=True),
        required=False,
        allow_null=True,
    )
    openings = serializers.IntegerField(min_value=1, max_value=500, required=False)

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
        ]

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
        return attrs


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
    }
    if detail:
        data["description"] = job.description
        data["seo"] = seo_block(job)
    return data
