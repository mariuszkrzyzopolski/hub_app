"""
Custom admin dashboard views for usage statistics.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Max
from gifts.models import GiftList, GiftClaim, GiftAuditLog
from events.models import Event, Role, RoleAssignment, EventAuditLog


@staff_member_required
def usage_statistics(request):
    """Display usage statistics for all gift lists and events."""
    # Gift list statistics
    gift_stats = []
    for gl in GiftList.objects.all().prefetch_related('items', 'audit_logs'):
        total = gl.items.count()
        claimed = GiftClaim.objects.filter(item__gift_list=gl).count()
        unique_claimants = (
            GiftClaim.objects.filter(item__gift_list=gl)
            .values('assignee_name')
            .distinct()
            .count()
        )
        last_activity = gl.audit_logs.order_by('-timestamp').first()
        completion = round((claimed / total * 100) if total > 0 else 0, 1)
        gift_stats.append({
            'name': gl.name,
            'slug': gl.slug,
            'total': total,
            'claimed': claimed,
            'completion_pct': completion,
            'unique_claimants': unique_claimants,
            'last_activity': last_activity.timestamp if last_activity else None,
            'is_active': gl.is_active,
            'is_archived': gl.is_archived,
        })

    # Event statistics
    event_stats = []
    for ev in Event.objects.all().prefetch_related('audit_logs'):
        total = Role.objects.filter(category__event=ev).count()
        assigned = RoleAssignment.objects.filter(role__category__event=ev).count()
        unique_assignees = (
            RoleAssignment.objects.filter(role__category__event=ev)
            .values('assignee_name')
            .distinct()
            .count()
        )
        last_activity = ev.audit_logs.order_by('-timestamp').first()
        completion = round((assigned / total * 100) if total > 0 else 0, 1)
        event_stats.append({
            'name': ev.name,
            'slug': ev.slug,
            'total': total,
            'assigned': assigned,
            'completion_pct': completion,
            'unique_assignees': unique_assignees,
            'last_activity': last_activity.timestamp if last_activity else None,
            'is_active': ev.is_active,
            'is_archived': ev.is_archived,
        })

    # Sort by completion percentage (ascending)
    gift_stats.sort(key=lambda x: x['completion_pct'])
    event_stats.sort(key=lambda x: x['completion_pct'])

    return render(request, 'admin/usage_statistics.html', {
        'title': 'Statystyki użycia',
        'gift_stats': gift_stats,
        'event_stats': event_stats,
    })