import uuid

from django.db import models
from django.utils.text import slugify

from .taxonomy_data import skill_slug


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    country = models.CharField(max_length=60, default="India")

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class JobLevel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=60, unique=True)
    rank = models.PositiveSmallIntegerField(unique=True)

    class Meta:
        ordering = ["rank"]

    def __str__(self) -> str:
        return self.name


class SkillKind(models.TextChoices):
    TECH = "tech", "Tech"
    NON_TECH = "non_tech", "Non-tech"


class Skill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    kind = models.CharField(max_length=10, choices=SkillKind.choices, default=SkillKind.TECH)
    category = models.CharField(max_length=60, blank=True, default="")
    synonyms = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.slug = skill_slug(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Company(models.Model):
    """A fictional hiring company (D-84). Shown on job pages; never a real company's name or logo."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    tagline = models.CharField(max_length=160, blank=True, default="")
    about = models.TextField(blank=True, default="")
    industry = models.CharField(max_length=80, blank=True, default="")
    size = models.CharField(max_length=40, blank=True, default="")
    founded = models.PositiveSmallIntegerField(null=True, blank=True)
    headquarters = models.CharField(max_length=100, blank=True, default="")
    offices = models.JSONField(default=list, blank=True)
    culture = models.TextField(blank=True, default="")
    benefits = models.JSONField(default=list, blank=True)
    # [{"step": "Shortlist", "detail": "..."}] in order.
    hiring_process = models.JSONField(default=list, blank=True)
    # Placeholder only, on the reserved .example domain.
    website = models.CharField(max_length=200, blank=True, default="")
    # Logo placeholder: initials on a colour, never an image of a real mark.
    logo_initials = models.CharField(max_length=3, blank=True, default="")
    logo_color = models.CharField(max_length=7, blank=True, default="#0B6E78")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        if not self.logo_initials:
            words = [w for w in self.name.replace(".", " ").split() if w[:1].isalpha()]
            self.logo_initials = "".join(w[0] for w in words[:2]).upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
