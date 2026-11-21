from django.utils.text import slugify
from rest_framework import serializers

from .models import Department, JobLevel, Location, Skill
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
