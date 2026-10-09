from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from core.session import clear_guest_name, get_guest_name
from gifts.models import GiftList, GiftClaim, GiftItem
from events.models import Event, RoleAssignment, Role


def change_name(request):
    """Clear the guest name from session and redirect to trigger name gate."""
    clear_guest_name(request)
    referer = request.META.get('HTTP_REFERER', reverse('home'))
    return redirect(referer)


class HomeView(View):
    """Catalogue homepage showing active gift lists and events with progress."""

    def get(self, request):
        guest_name = get_guest_name(request)

        # Active gift lists with progress
        gift_lists = GiftList.objects.filter(is_active=True, is_archived=False)
        gift_list_data = []
        for gl in gift_lists:
            items = gl.items.all()
            total = items.count()
            claimed = GiftClaim.objects.filter(item__in=items).count()
            gift_list_data.append({
                'slug': gl.slug,
                'name': gl.name,
                'total': total,
                'claimed': claimed,
            })

        # Active events with progress
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

        return render(request, 'home.html', {
            'guest_name': guest_name,
            'gift_lists': gift_list_data,
            'events': event_data,
        })