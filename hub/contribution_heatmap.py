"""
Contribution heatmap — owner-facing admin view showing which guests claimed/assigned
the most across all gift lists and events.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count
from gifts.models import GiftClaim, GiftAuditLog
from events.models import RoleAssignment, EventAuditLog


@staff_member_required
def contribution_heatmap(request):
    """Display contribution heatmap — per-guest contribution rankings."""
    # ===== Gift contributions =====
    # Per-guest total gift claims with per-list breakdown
    gift_guest_counts = (
        GiftClaim.objects.values('assignee_name')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    max_gift = max((g['total'] for g in gift_guest_counts), default=0)

    # Build combined gift data with breakdown inline
    gift_data = []
    for gc in gift_guest_counts:
        name = gc['assignee_name']
        per_list = list(
            GiftClaim.objects.filter(assignee_name=name)
            .values('item__gift_list__name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        gift_data.append({
            'assignee_name': name,
            'total': gc['total'],
            'breakdown': per_list,
        })

    # ===== Event contributions =====
    # Per-guest total event assignments with per-event breakdown
    event_guest_counts = (
        RoleAssignment.objects.values('assignee_name')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    max_event = max((e['total'] for e in event_guest_counts), default=0)

    # Build combined event data with breakdown inline
    event_data = []
    for ec in event_guest_counts:
        name = ec['assignee_name']
        per_event = list(
            RoleAssignment.objects.filter(assignee_name=name)
            .values('role__category__event__name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        event_data.append({
            'assignee_name': name,
            'total': ec['total'],
            'breakdown': per_event,
        })

    return render(request, 'admin/contribution_heatmap.html', {
        'title': 'Mapa wkładu gości',
        'gift_data': gift_data,
        'event_data': event_data,
        'max_gift': max_gift or 1,
        'max_event': max_event or 1,
    })
