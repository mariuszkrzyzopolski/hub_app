from django import forms
from django.contrib import admin
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import F, Count
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.shortcuts import get_object_or_404
from .models import GiftList, GiftItem, GiftClaim, GiftAuditLog


class GiftItemInline(admin.TabularInline):
    model = GiftItem
    extra = 1
    fields = ['name', 'description', 'order']


class GiftListForm(forms.ModelForm):
    password = forms.CharField(
        label='Password',
        required=False,
        widget=forms.PasswordInput(render_value=True),
        min_length=4,
        max_length=20,
    )

    class Meta:
        model = GiftList
        fields = '__all__'

    def save(self, commit=True):
        instance = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            if not instance.pk:
                instance.password_hash = make_password(password)
            else:
                old = GiftList.objects.filter(pk=instance.pk).values('password_hash').first()
                if old and not check_password(password, old['password_hash']):
                    instance.password_hash = make_password(password)
                    GiftList.objects.filter(pk=instance.pk).update(
                        password_version=F('password_version') + 1
                    )
        if commit:
            instance.save()
        return instance


@admin.register(GiftList)
class GiftListAdmin(admin.ModelAdmin):
    form = GiftListForm
    list_display = ['name', 'completion_indicator', 'is_active', 'is_archived', 'event_date', 'created_at']
    list_filter = ['is_active', 'is_archived', 'event_date']
    search_fields = ['name', 'slug', 'description']
    inlines = [GiftItemInline]
    readonly_fields = ['password_version', 'password_hash', 'share_info']
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description', 'event_date')
        }),
        ('Access', {
            'fields': ('password', 'password_version', 'is_active', 'is_archived')
        }),
        ('Share Info', {
            'fields': ('share_info',),
            'classes': ('wide',),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('items', 'audit_logs')

    def completion_indicator(self, obj):
        """Visual completion indicator for gift lists."""
        total = obj.items.count()
        claimed = GiftClaim.objects.filter(item__gift_list=obj).count()
        pct = round((claimed / total * 100) if total > 0 else 0)
        bar_color = '#28a745' if pct > 0 else '#e5e7eb'
        if pct >= 100:
            bar_color = '#28a745'
        elif pct >= 50:
            bar_color = '#e67e22'
        return format_html(
            '<span class="completion-indicator">'
            '<span class="completion-bar">'
            '<span class="completion-bar-fill" style="width:{}%;background:{};"></span>'
            '</span>'
            '<span style="font-size:0.8rem;color:#6b7280;">{}/{} ({}%)</span>'
            '</span>',
            pct, bar_color, claimed, total, pct
        )
    completion_indicator.short_description = 'Postęp'
    completion_indicator.admin_order_field = 'name'

    def view_on_site_link(self, obj):
        """Link to view the gift list on the public site."""
        url = reverse('gift-list', kwargs={'slug': obj.slug})
        return format_html(
            '<a class="view-on-site" href="{}" target="_blank">🔗 Podgląd</a>',
            url
        )
    view_on_site_link.short_description = ''

    def share_info(self, obj):
        """Share info panel displaying copyable stats."""
        total = obj.items.count()
        claimed = GiftClaim.objects.filter(item__gift_list=obj).count()
        unique_claimants = (
            GiftClaim.objects.filter(item__gift_list=obj)
            .values_list('assignee_name', flat=True)
            .distinct().count()
        )
        last_activity = obj.audit_logs.order_by('-timestamp').first()
        last_activity_str = (
            last_activity.timestamp.strftime('%Y-%m-%d %H:%M')
            if last_activity else 'Brak'
        )
        stats = (
            f"Lista: {obj.name}\n"
            f"Zajęte: {claimed}/{total}\n"
            f"Unikalni goście: {unique_claimants}\n"
            f"Ostatnia aktywność: {last_activity_str}\n"
            f"Link: /gifts/{obj.slug}/"
        )
        return format_html(
            '<pre style="background:#f5f5f5;padding:1em;border-radius:4px;cursor:pointer;'
            'font-size:0.9rem;" onclick="navigator.clipboard.writeText(this.textContent)">'
            '{}</pre>',
            stats
        )
    share_info.short_description = 'Udostępnij (kliknij, by skopiować)'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/archive/',
                self.admin_site.admin_view(self.archive_view),
                name='gifts_giftlist_archive',
            ),
        ]
        return custom_urls + urls

    def archive_view(self, request, object_id):
        """Manually archive a gift list."""
        obj = get_object_or_404(GiftList, pk=object_id)
        obj.is_archived = True
        obj.save()
        self.message_user(request, f'Lista "{obj.name}" została zarchiwizowana.')
        return HttpResponseRedirect(
            reverse('admin:gifts_giftlist_changelist')
        )


@admin.register(GiftClaim)
class GiftClaimAdmin(admin.ModelAdmin):
    list_display = ['item', 'assignee_name', 'claimed_at']
    list_filter = ['claimed_at']
    search_fields = ['assignee_name', 'item__name']
    readonly_fields = ['claimed_at', 'updated_at']


# --- Gift Audit Log Admin with Restore ---

def restore_gift_claim(modeladmin, request, queryset):
    """Action: restore selected deleted audit log entries."""
    for entry in queryset:
        if entry.is_deleted:
            _perform_gift_restore(entry)
restore_gift_claim.short_description = "Przywróć zaznaczone usunięte przypisania"


def _perform_gift_restore(entry):
    """Restore a single deleted gift claim."""
    from django.utils import timezone
    if entry.item and not GiftClaim.objects.filter(item=entry.item).exists():
        GiftClaim.objects.create(
            item=entry.item,
            assignee_name=entry.assignee_name,
            session_id=entry.session_id,
        )
    entry.is_deleted = False
    entry.restored_at = timezone.now()
    entry.save()


@admin.register(GiftAuditLog)
class GiftAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'action', 'assignee_name', 'gift_list', 'item', 'timestamp',
        'is_deleted', 'restore_button'
    ]
    list_filter = ['action', 'is_deleted', 'timestamp']
    search_fields = ['assignee_name', 'action', 'gift_list__name']
    readonly_fields = ['action', 'assignee_name', 'session_id', 'timestamp',
                       'is_deleted', 'restored_at']
    actions = [restore_gift_claim]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/restore/',
                self.admin_site.admin_view(self.restore_view),
                name='gifts_giftauditlog_restore',
            ),
        ]
        return custom_urls + urls

    def restore_view(self, request, object_id):
        """One-click restore of a deleted audit log entry."""
        entry = get_object_or_404(GiftAuditLog, pk=object_id)
        if entry.is_deleted:
            _perform_gift_restore(entry)
            self.message_user(
                request,
                f'Przywrócono przypisanie dla "{entry.item.name if entry.item else "usuniętego przedmiotu"}".'
            )
        else:
            self.message_user(request, 'To przypisanie nie zostało usunięte.')
        return HttpResponseRedirect(
            reverse('admin:gifts_giftauditlog_changelist')
        )

    def restore_button(self, obj):
        """Render a restore link for deleted entries."""
        if obj.is_deleted:
            url = reverse('admin:gifts_giftauditlog_restore', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background:#28a745;color:white;'
                'padding:2px 8px;border-radius:3px;text-decoration:none;">Przywróć</a>',
                url
            )
        return ''
    restore_button.short_description = 'Przywróć'
    restore_button.allow_tags = True