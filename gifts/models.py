from django.db import models
from django.utils.text import slugify
from slugify import slugify as python_slugify
from core.models import PasswordGatedModel, AuditLogEntry


class GiftList(PasswordGatedModel):
    """A gift list for a specific occasion."""

    class Meta:
        verbose_name = 'Gift List'
        verbose_name_plural = 'Gift Lists'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = python_slugify(self.name)[:200]
        super().save(*args, **kwargs)


class GiftItem(models.Model):
    """An individual gift item within a gift list."""
    gift_list = models.ForeignKey(GiftList, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.name

    @property
    def is_claimed(self):
        return hasattr(self, 'claim') and self.claim is not None


class GiftClaim(models.Model):
    """A claim on a gift item by a guest."""
    item = models.OneToOneField(GiftItem, on_delete=models.CASCADE, related_name='claim')
    assignee_name = models.CharField(max_length=200)
    session_id = models.CharField(max_length=255)
    claimed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.item.name} → {self.assignee_name}"


class GiftAuditLog(AuditLogEntry):
    """Audit log for gift list actions."""
    gift_list = models.ForeignKey(GiftList, on_delete=models.CASCADE, related_name='audit_logs')
    item = models.ForeignKey(GiftItem, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} - {self.assignee_name} at {self.timestamp}"