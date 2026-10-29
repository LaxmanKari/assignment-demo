import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


def upload_path(instance, filename):
    ext = Path(filename).suffix.lower()
    return f"documents/{instance.owner_id}/{uuid.uuid4().hex}{ext}"


class Document(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to=upload_path, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents"
    )

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title


class QueryLog(models.Model):
    query_text = models.TextField()
    result_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="queries"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.query_text[:50]


class UserSession(models.Model):
    """One row per login. `token` stores the refresh token's jti (its unique ID)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions"
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"{self.user} @ {self.created_at:%Y-%m-%d %H:%M}"