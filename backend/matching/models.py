import uuid

from django.db import models

from core.fields import EncryptedTextField


class ParsedProfile(models.Model):
    """What the extractor found in one application's resume (versioned)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        "applications.Application", on_delete=models.CASCADE, related_name="parsed_profile"
    )
    version = models.PositiveSmallIntegerField()
    # [{"slug", "name", "section"}]: skill names and section labels only, no free text.
    skills = models.JSONField(default=list)
    # JSON list of {"slug", "snippet"}; snippets are resume text, so encrypted.
    evidence = EncryptedTextField(blank=True, default="[]")
    sections_found = models.JSONField(default=list)
    experience_years = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    internship_months = models.PositiveSmallIntegerField(null=True, blank=True)
    parsed_at = models.DateTimeField(auto_now=True)


class FitScore(models.Model):
    """Stored fit score with its explanation (versioned)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        "applications.Application", on_delete=models.CASCADE, related_name="fit_score"
    )
    score = models.PositiveSmallIntegerField(db_index=True)
    band = models.CharField(max_length=10, db_index=True)
    explanation = models.JSONField(default=dict)
    version = models.PositiveSmallIntegerField()
    requirements_hash = models.CharField(max_length=64)
    computed_at = models.DateTimeField(auto_now=True)
