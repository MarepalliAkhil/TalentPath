"""Week 4A: a person's own resume on their profile, used for the skill-gap career map and
one-click internal applications. Text and evidence are encrypted; the file is stored
compressed and encrypted like application resumes. The owner can delete it at any time."""

import uuid

from django.conf import settings
from django.db import models

from core.fields import EncryptedTextField


class CareerProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="career_profile"
    )
    resume_file = models.ForeignKey(
        "files.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resume_filename = models.CharField(max_length=120, blank=True, default="")
    resume_text = EncryptedTextField(blank=True, default="")
    # Parsed by the same extractor as applications: [{slug, name, section}], evidence snippets encrypted.
    skills = models.JSONField(default=list, blank=True)
    evidence = EncryptedTextField(blank=True, default="")
    experience_years = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    extractor_version = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Career profile of {self.user_id}"
