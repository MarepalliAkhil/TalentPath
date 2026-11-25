import re

from django.utils.text import slugify
from rest_framework import serializers

from .models import Company, Department, JobLevel, Location, Skill
from .taxonomy_data import skill_slug


class _UniqueSlugMixin:
    slug_fn = staticmethod(slugify)

    def validate_name(self, value):
        value = value.strip()
        slug = self.slug_fn(value)
        if not slug:
            raise serializers.ValidationError("Name must contain letters or numbers.")
        qs = self.Meta.model.objects.filter(slug=slug)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("An entry with this name already exists.")
        return value


class DepartmentSerializer(_UniqueSlugMixin, serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "slug"]
        read_only_fields = ["id", "slug"]


class LocationSerializer(_UniqueSlugMixin, serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "name", "slug", "country"]
        read_only_fields = ["id", "slug"]


class JobLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobLevel
        fields = ["id", "name", "rank"]
        read_only_fields = ["id"]


class SkillSerializer(_UniqueSlugMixin, serializers.ModelSerializer):
    slug_fn = staticmethod(skill_slug)
    synonyms = serializers.ListField(
        child=serializers.CharField(max_length=60), required=False, max_length=20
    )

    class Meta:
        model = Skill
        fields = ["id", "name", "slug", "kind", "category", "synonyms"]
        read_only_fields = ["id", "slug"]


class CompanySerializer(_UniqueSlugMixin, serializers.ModelSerializer):
    """Admin manages fictional companies (D-84). Real company names and real websites are refused."""

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "slug",
            "tagline",
            "about",
            "industry",
            "size",
            "founded",
            "headquarters",
            "offices",
            "culture",
            "benefits",
            "hiring_process",
            "website",
            "logo_initials",
            "logo_color",
        ]
        read_only_fields = ["id", "slug"]

    def validate_name(self, value):
        from .fictional import looks_real

        value = super().validate_name(value)
        if looks_real(value):
            raise serializers.ValidationError(
                "Use a fictional company name; real company names are not allowed."
            )
        return value

    def validate_website(self, value):
        value = (value or "").strip()
        if value and not re.fullmatch(r"https://[a-z0-9.-]+\.example(/.*)?", value):
            raise serializers.ValidationError("Use a placeholder address on the .example domain.")
        return value

    def validate_logo_color(self, value):
        if value and not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise serializers.ValidationError("Use a colour like #0B6E78.")
        return value

    def _texts(self, value, field):
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            raise serializers.ValidationError("Give a list of short texts.")
        if len(value) > 30 or any(len(v) > 300 for v in value):
            raise serializers.ValidationError("Keep it to 30 items of up to 300 characters.")
        return [v.strip() for v in value]

    def validate_offices(self, value):
        return self._texts(value, "offices")

    def validate_benefits(self, value):
        return self._texts(value, "benefits")

    def validate_hiring_process(self, value):
        if not isinstance(value, list) or len(value) > 12:
            raise serializers.ValidationError("Give up to 12 steps.")
        out = []
        for step in value:
            if not isinstance(step, dict) or not str(step.get("step", "")).strip():
                raise serializers.ValidationError("Each step needs a name.")
            out.append(
                {"step": str(step["step"]).strip()[:60], "detail": str(step.get("detail", "")).strip()[:300]}
            )
        return out
