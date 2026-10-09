from django.db import models
from slugify import slugify as python_slugify
from core.models import PasswordGatedModel, AuditLogEntry


class Event(PasswordGatedModel):
    """An event with assignable roles."""

    class Meta:
        verbose_name = 'Event'
        verbose_name_plural = 'Events'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = python_slugify(self.name)[:200]
        super().save(*args, **kwargs)


class RoleCategory(models.Model):
    """A category grouping roles within an event."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=200)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name_plural = 'Role categories'

    def __str__(self):
        return self.name

    @property
    def is_claimed(self):
        """Check if any role in this category has a via_category claim."""
        return self.roles.filter(assignment__via_category=True).exists()

    @property
    def claimed_by(self):
        """Return the name of the person who claimed the category, if any."""
        assignment = self.roles.filter(assignment__via_category=True).select_related('assignment').first()
        if assignment and hasattr(assignment, 'assignment'):
            return assignment.assignment.assignee_name
        return None


class Role(models.Model):
    """An individual role within a category."""
    category = models.ForeignKey(RoleCategory, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.name

    @property
    def is_assigned(self):
        return hasattr(self, 'assignment') and self.assignment is not None

    @property
    def is_locked(self):
        """A role is locked if another role in the same category has via_category=True."""
        return self.category.roles.filter(assignment__via_category=True).exclude(
            id=self.id if self.pk else -1
        ).exists()


class RoleAssignment(models.Model):
    """An assignment of a guest to a role."""
    role = models.OneToOneField(Role, on_delete=models.CASCADE, related_name='assignment')
    assignee_name = models.CharField(max_length=200)
    session_id = models.CharField(max_length=255)
    via_category = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.role.name} → {self.assignee_name}"


class EventAuditLog(AuditLogEntry):
    """Audit log for event actions."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='audit_logs')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} - {self.assignee_name} at {self.timestamp}"