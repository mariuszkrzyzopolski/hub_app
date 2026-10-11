from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from django.views.generic import View
from core.mixins import PasswordGatedViewMixin
from core.session import get_guest_name
from .models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog
from . import assignments
from .exceptions import (
    RoleCollisionError,
    RoleAlreadyAssignedError,
    CategoryCollisionError,
    CategoryLockedError,
    RoleNotFoundError,
    CategoryNotFoundError,
    AssignmentNotFoundError,
)



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
        session_id = request.session.session_key or ''

        try:
            if action == 'assign':
                role_id = request.POST.get('role_id')
                assignments.assign_role(event, role_id, guest_name, session_id)

            elif action == 'assign_category':
                category_id = request.POST.get('category_id')
                assignments.assign_category(event, category_id, guest_name, session_id)

            elif action == 'unclaim_category':
                category_id = request.POST.get('category_id')
                assignments.unclaim_category(event, category_id, guest_name, session_id)

            elif action == 'edit':
                assignment_id = request.POST.get('assignment_id')
                assignments.edit_assignment(event, assignment_id, guest_name, session_id)

            elif action == 'delete':
                role_id = request.POST.get('role_id')
                try:
                    assignments.delete_assignment(event, role_id, session_id)
                except AssignmentNotFoundError:
                    pass

            elif action == 'update_claims':
                old_name = request.POST.get('old_name', '')
                if old_name:
                    assignments.update_guest_assignments(event, old_name, guest_name, session_id)

        except RoleAlreadyAssignedError:
            return self._render_error(request, event, 'Ta rola jest już przypisana.')
        except CategoryCollisionError:
            return self._render_error(request, event, 'Kategoria została właśnie zajęta. Odśwież stronę i spróbuj ponownie.')
        except RoleCollisionError:
            return self._render_error(request, event, 'Ta rola została właśnie przypisana. Odśwież stronę i spróbuj ponownie.')
        except CategoryLockedError:
            return self._render_error(
                request,
                event,
                'Ta kategoria jest zarezerwowana. Aby zmienić role, najpierw zwolnij kategorię.',
            )
        except (RoleNotFoundError, CategoryNotFoundError, AssignmentNotFoundError):
            raise Http404("Role, category or assignment not found")

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
