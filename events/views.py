from django.db import transaction, DatabaseError
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from django.views.generic import View
from core.mixins import PasswordGatedViewMixin
from core.session import get_guest_name
from .models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog


@method_decorator(never_cache, name='dispatch')
class EventDetailView(PasswordGatedViewMixin, View):
    password_model = Event
    template_name = 'events/event_roles.html'

    def get(self, request, slug):
        event = get_object_or_404(Event, slug=slug)

        if event.is_archived:
            return render(request, 'core/archived.html', {
                'guest_name': get_guest_name(request),
            })

        categories = event.categories.prefetch_related('roles__assignment').all()
        has_roles = any(cat.roles.count() > 0 for cat in categories)
        if not has_roles:
            return render(request, 'core/in_progress.html', {
                'guest_name': get_guest_name(request),
            })

        guest_name = get_guest_name(request)
        total_roles = sum(cat.roles.count() for cat in categories)
        assigned_roles = sum(
            1 for cat in categories
            for role in cat.roles.all()
            if hasattr(role, 'assignment') and role.assignment is not None
        )
        return render(request, self.template_name, {
            'event': event,
            'categories': categories,
            'guest_name': guest_name,
            'total_roles': total_roles,
            'assigned_roles': assigned_roles,
        })

    def post(self, request, slug):
        event = get_object_or_404(Event, slug=slug)
        action = request.POST.get('action')
        guest_name = get_guest_name(request)

        if action == 'assign':
            role_id = request.POST.get('role_id')
            role = get_object_or_404(Role, id=role_id, category__event=event)
            try:
                with transaction.atomic():
                    # Lock only the Role row — select_related on reverse OneToOne
                    # can cause lock failures on non-existent related rows
                    role_locked = Role.objects.select_for_update(
                        nowait=True
                    ).get(id=role.id)
                    # Check for existing assignment separately
                    existing_assignment = RoleAssignment.objects.filter(role=role_locked).first()
                    if existing_assignment is not None:
                        return self._render_error(request, event, 'Ta rola jest już przypisana.')
                    if role_locked.is_locked:
                        return self._render_error(request, event, 'Ta kategoria jest zarezerwowana. Aby zmienić role, najpierw zwolnij kategorię.')
                    RoleAssignment.objects.create(
                        role=role_locked,
                        assignee_name=guest_name,
                        session_id=request.session.session_key or '',
                    )
                    EventAuditLog.objects.create(
                        event=event,
                        role=role_locked,
                        action='assign',
                        assignee_name=guest_name,
                        session_id=request.session.session_key or '',
                    )
            except DatabaseError:
                return self._render_error(request, event, 'Ta rola została właśnie przypisana. Odśwież stronę i spróbuj ponownie.')

        elif action == 'assign_category':
            category_id = request.POST.get('category_id')
            category = get_object_or_404(RoleCategory, id=category_id, event=event)
            try:
                with transaction.atomic():
                    roles = Role.objects.filter(category=category).select_for_update(
                        nowait=True
                    ).order_by('id')
                    for role in roles:
                        if not hasattr(role, 'assignment') or role.assignment is None:
                            RoleAssignment.objects.create(
                                role=role,
                                assignee_name=guest_name,
                                session_id=request.session.session_key or '',
                                via_category=True,
                            )
                    EventAuditLog.objects.create(
                        event=event,
                        action='assign_category',
                        assignee_name=guest_name,
                        session_id=request.session.session_key or '',
                    )
            except DatabaseError:
                return self._render_error(request, event, 'Kategoria została właśnie zajęta. Odśwież stronę i spróbuj ponownie.')

        elif action == 'unclaim_category':
            category_id = request.POST.get('category_id')
            category = get_object_or_404(RoleCategory, id=category_id, event=event)
            with transaction.atomic():
                assignments = RoleAssignment.objects.filter(
                    role__category=category, via_category=True
                ).select_for_update().order_by('id')
                for assignment in assignments:
                    assignment.delete()
                EventAuditLog.objects.create(
                    event=event,
                    action='unclaim_category',
                    assignee_name=guest_name,
                    session_id=request.session.session_key or '',
                )

        elif action == 'edit':
            assignment_id = request.POST.get('assignment_id')
            assignment = get_object_or_404(RoleAssignment, id=assignment_id, role__category__event=event)
            old_name = assignment.assignee_name
            assignment.assignee_name = guest_name
            assignment.save()
            EventAuditLog.objects.create(
                event=event,
                role=assignment.role,
                action='edit',
                assignee_name=f"{old_name} → {guest_name}",
                session_id=request.session.session_key or '',
            )

        elif action == 'delete':
            role_id = request.POST.get('role_id')
            role = get_object_or_404(Role, id=role_id, category__event=event)
            assignment = RoleAssignment.objects.filter(role=role).first()
            if assignment:
                assignee = assignment.assignee_name
                assignment.delete()
                EventAuditLog.objects.create(
                    event=event,
                    role=role,
                    action='delete',
                    assignee_name=assignee,
                    session_id=request.session.session_key or '',
                    is_deleted=True,
                )

        elif action == 'update_claims':
            old_name = request.POST.get('old_name', '')
            if old_name:
                updated = RoleAssignment.objects.filter(
                    role__category__event=event, assignee_name=old_name
                ).update(assignee_name=guest_name)
                if updated > 0:
                    EventAuditLog.objects.create(
                        event=event,
                        action='update_claims',
                        assignee_name=f"{old_name} → {guest_name}",
                        session_id=request.session.session_key or '',
                    )

        return redirect('event-roles', slug=slug)

    def _render_error(self, request, event, message):
        categories = event.categories.prefetch_related('roles__assignment').all()
        return render(request, self.template_name, {
            'event': event,
            'categories': categories,
            'guest_name': get_guest_name(request),
            'error': message,
        })


def event_roles_view(request, slug):
    view = EventDetailView.as_view()
    return view(request, slug=slug)


def event_index_view(request):
    """List all active events."""
    from django.shortcuts import render
    from core.session import get_guest_name
    from .models import Role, RoleAssignment
    events = Event.objects.filter(is_active=True, is_archived=False)
    event_data = []
    for ev in events:
        total = Role.objects.filter(category__event=ev).count()
        assigned = RoleAssignment.objects.filter(role__category__event=ev).count()
        event_data.append({
            'slug': ev.slug,
            'name': ev.name,
            'total': total,
            'assigned': assigned,
        })
    return render(request, 'events/event_index.html', {
        'guest_name': get_guest_name(request),
        'events': event_data,
    })


def event_count_json(request, slug):
    """JSON endpoint returning current assignment counts for auto-refresh."""
    from django.http import JsonResponse
    from .models import Role, RoleAssignment
    event = get_object_or_404(Event, slug=slug)
    total = Role.objects.filter(category__event=event).count()
    assigned = RoleAssignment.objects.filter(role__category__event=event).count()
    return JsonResponse({
        'total': total,
        'assigned': assigned,
    })
