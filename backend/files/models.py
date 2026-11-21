import uuid

from django.conf import settings
from django.db import models


class StoredFile(models.Model):
    """Uploaded file kept in PostgreSQL (free mode): zlib-compressed, then AES-GCM encrypted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stored_files")
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    data = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.original_name
