from django import forms
from django.contrib import admin
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import F, Count
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.shortcuts import get_object_or_404
from .models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog


class RoleInline(admin.TabularInline):
    model = Role
    extra = 1
    fields = ['name', 'description', 'order']


class RoleCategoryInline(admin.TabularInline):
    model = RoleCategory
    extra = 1
    fields = ['name', 'order']
    show_change_link = True


class EventForm(forms.ModelForm):
    password = forms.CharField(
        label='Password',
        required=False,
        widget=forms.PasswordInput(render_value=True),
        min_length=4,
        max_length=20,
    )

    class Meta:
        model = Event
        fields = '__all__'

    def save(self, commit=True):
        instance = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            if not instance.pk:
                instance.password_hash = make_password(password)
            else:
                old = Event.objects.filter(pk=instance.pk).values('password_hash').first()
                if old and not check_password(password, old['password_hash']):
                    instance.password_hash = make_password(password)
                    Event.objects.filter(pk=instance.pk).update(
                        password_version=F('password_version') + 1
                    )
        if commit:
            instance.save()
        return instance


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    form = EventForm
    list_display = ['name', 'completion_indicator', 'is_active', 'is_archived', 'event_date', 'created_at']
    list_filter = ['is_active', 'is_archived', 'event_date']
    search_fields = ['name', 'slug', 'description']
    inlines = [RoleCategoryInline]
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
        return qs.prefetch_related('audit_logs')

    def completion_indicator(self, obj):
        """Visual completion indicator for events."""
        from .models import Role, RoleAssignment
        total = Role.objects.filter(category__event=obj).count()
        assigned = RoleAssignment.objects.filter(role__category__event=obj).count()
        pct = round((assigned / total * 100) if total > 0 else 0)
        return format_html(
            '<span class="completion-indicator">'
            '<span class="completion-bar">'
            '<span class="completion-bar-fill" style="width:{}%;"></span>'
            '</span>'
            '<span style="font-size:0.8rem;color:#6b7280;">{}/{} ({}%)</span>'
            '</span>',
            pct, assigned, total, pct
        )
    completion_indicator.short_description = 'Postęp'

    def view_on_site_link(self, obj):
        """Link to view the event on the public site."""
        url = reverse('event-roles', kwargs={'slug': obj.slug})
        return format_html(
            '<a class="view-on-site" href="{}" target="_blank">🔗 Podgląd</a>',
            url
        )
    view_on_site_link.short_description = ''

    def share_info(self, obj):
        """Share info panel displaying copyable stats."""
        from .models import Role, RoleAssignment
        total = Role.objects.filter(category__event=obj).count()
        assigned = RoleAssignment.objects.filter(role__category__event=obj).count()
        unique_assignees = (
            RoleAssignment.objects.filter(role__category__event=obj)
            .values_list('assignee_name', flat=True)
            .distinct().count()
        )
        last_activity = obj.audit_logs.order_by('-timestamp').first()
        last_activity_str = (
            last_activity.timestamp.strftime('%Y-%m-%d %H:%M')
            if last_activity else 'Brak'
        )
        stats = (
            f"Wydarzenie: {obj.name}\n"
            f"Przypisane: {assigned}/{total}\n"
            f"Unikalni goście: {unique_assignees}\n"
            f"Ostatnia aktywność: {last_activity_str}\n"
            f"Link: /events/{obj.slug}/"
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
                name='events_event_archive',
            ),
        ]
        return custom_urls + urls

    def archive_view(self, request, object_id):
        """Manually archive an event."""
        obj = get_object_or_404(Event, pk=object_id)
        obj.is_archived = True
        obj.save()
        self.message_user(request, f'Wydarzenie "{obj.name}" zostało zarchiwizowane.')
        return HttpResponseRedirect(
            reverse('admin:events_event_changelist')
        )


@admin.register(RoleCategory)
class RoleCategoryAdmin(admin.ModelAdmin):
    inlines = [RoleInline]
    list_display = ['name', 'event', 'order']
    list_filter = ['event']
    search_fields = ['name']


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ['role', 'assignee_name', 'via_category', 'assigned_at']
    list_filter = ['via_category', 'assigned_at']
    search_fields = ['assignee_name', 'role__name']
    readonly_fields = ['assigned_at', 'updated_at']


# --- Event Audit Log Admin with Restore ---

def restore_event_assignment(modeladmin, request, queryset):
    """Action: restore selected deleted audit log entries."""
    for entry in queryset:
        if entry.is_deleted:
            _perform_event_restore(entry)
restore_event_assignment.short_description = "Przywróć zaznaczone usunięte przypisania"


def _perform_event_restore(entry):
    """Restore a single deleted event role assignment."""
    from django.utils import timezone
    if entry.role and not RoleAssignment.objects.filter(role=entry.role).exists():
        RoleAssignment.objects.create(
            role=entry.role,
            assignee_name=entry.assignee_name,
            session_id=entry.session_id,
        )
    entry.is_deleted = False
    entry.restored_at = timezone.now()
    entry.save()


@admin.register(EventAuditLog)
class EventAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'action', 'assignee_name', 'event', 'role', 'timestamp',
        'is_deleted', 'restore_button'
    ]
    list_filter = ['action', 'is_deleted', 'timestamp']
    search_fields = ['assignee_name', 'action', 'event__name']
    readonly_fields = ['action', 'assignee_name', 'session_id', 'timestamp',
                       'is_deleted', 'restored_at']
    actions = [restore_event_assignment]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/restore/',
                self.admin_site.admin_view(self.restore_view),
                name='events_eventauditlog_restore',
            ),
        ]
        return custom_urls + urls

    def restore_view(self, request, object_id):
        """One-click restore of a deleted audit log entry."""
        entry = get_object_or_404(EventAuditLog, pk=object_id)
        if entry.is_deleted:
            _perform_event_restore(entry)
            self.message_user(
                request,
                f'Przywrócono przypisanie dla "{entry.role.name if entry.role else "usuniętej roli"}".'
            )
        else:
            self.message_user(request, 'To przypisanie nie zostało usunięte.')
        return HttpResponseRedirect(
            reverse('admin:events_eventauditlog_changelist')
        )

    def restore_button(self, obj):
        """Render a restore link for deleted entries."""
        if obj.is_deleted:
            url = reverse('admin:events_eventauditlog_restore', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background:#28a745;color:white;'
                'padding:2px 8px;border-radius:3px;text-decoration:none;">Przywróć</a>',
                url
            )
        return ''
    restore_button.short_description = 'Przywróć'
    restore_button.allow_tags = True