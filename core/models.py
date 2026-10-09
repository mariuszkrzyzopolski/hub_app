from django.db import models


class PasswordGatedModel(models.Model):
    """Abstract base for models that require password access."""
    slug = models.SlugField(max_length=200, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    password_hash = models.CharField(max_length=255, default='')
    password_version = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    event_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class AuditLogEntry(models.Model):
    """Abstract base for audit log entries."""
    action = models.CharField(max_length=50)
    assignee_name = models.CharField(max_length=200)
    session_id = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    restored_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ['-timestamp']


class GuestName(models.Model):
    """Globally unique guest name registry."""
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name