from django.db import transaction, DatabaseError
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from django.views.generic import View
from core.mixins import PasswordGatedViewMixin
from core.session import get_guest_name
from .models import GiftList, GiftItem, GiftClaim, GiftAuditLog


@method_decorator(never_cache, name='dispatch')
class GiftListView(PasswordGatedViewMixin, View):
    password_model = GiftList
    template_name = 'gifts/gift_list.html'

    def get(self, request, slug):
        gift_list = get_object_or_404(GiftList, slug=slug)

        if gift_list.is_archived:
            return render(request, 'core/archived.html', {
                'guest_name': get_guest_name(request),
            })

        items = gift_list.items.all()
        if not items.exists():
            return render(request, 'core/in_progress.html', {
                'guest_name': get_guest_name(request),
            })

        # Explicitly fetch claims and attach to items — select_related on reverse
        # OneToOne is unreliable; dict lookup guarantees the claim accessor works.
        claims = {c.item_id: c for c in GiftClaim.objects.filter(item__in=items)}
        for item in items:
            if item.id in claims:
                item.claim = claims[item.id]

        guest_name = get_guest_name(request)
        claimed = sum(1 for i in items if hasattr(i, 'claim') and i.claim is not None)
        return render(request, self.template_name, {
            'gift_list': gift_list,
            'items': items,
            'guest_name': guest_name,
            'total_items': items.count(),
            'claimed_items': claimed,
        })

    def post(self, request, slug):
        gift_list = get_object_or_404(GiftList, slug=slug)
        action = request.POST.get('action')
        guest_name = get_guest_name(request)

        if action == 'claim':
            item_id = request.POST.get('item_id')
            item = get_object_or_404(GiftItem, id=item_id, gift_list=gift_list)
            try:
                with transaction.atomic():
                    # Lock only the GiftItem row — select_related on reverse OneToOne
                    # can cause lock failures on non-existent related rows
                    item_locked = GiftItem.objects.select_for_update(
                        nowait=True
                    ).get(id=item.id)
                    # Check for existing claim separately
                    existing_claim = GiftClaim.objects.filter(item=item_locked).first()
                    if existing_claim is not None:
                        return self._render_gift_list(request, gift_list, guest_name,
                            'Ten prezent został właśnie zajęty. Odśwież stronę i wybierz inny.')
                    GiftClaim.objects.create(
                        item=item_locked,
                        assignee_name=guest_name,
                        session_id=request.session.session_key or '',
                    )
                    GiftAuditLog.objects.create(
                        gift_list=gift_list,
                        item=item_locked,
                        action='claim',
                        assignee_name=guest_name,
                        session_id=request.session.session_key or '',
                    )
            except DatabaseError:
                return self._render_gift_list(request, gift_list, guest_name,
                    'Ten prezent został właśnie zajęty. Odśwież stronę i wybierz inny.')

        elif action == 'edit':
            claim_id = request.POST.get('claim_id')
            claim = get_object_or_404(GiftClaim, id=claim_id, item__gift_list=gift_list)
            old_name = claim.assignee_name
            claim.assignee_name = guest_name
            claim.save()
            GiftAuditLog.objects.create(
                gift_list=gift_list,
                item=claim.item,
                action='edit',
                assignee_name=f"{old_name} → {guest_name}",
                session_id=request.session.session_key or '',
            )

        elif action == 'delete':
            item_id = request.POST.get('item_id')
            item = get_object_or_404(GiftItem, id=item_id, gift_list=gift_list)
            claim = GiftClaim.objects.filter(item=item).first()
            if claim:
                assignee = claim.assignee_name
                claim.delete()
                GiftAuditLog.objects.create(
                    gift_list=gift_list,
                    item=item,
                    action='delete',
                    assignee_name=assignee,
                    session_id=request.session.session_key or '',
                    is_deleted=True,
                )

        elif action == 'update_claims':
            old_name = request.POST.get('old_name', '')
            if old_name:
                updated = GiftClaim.objects.filter(
                    item__gift_list=gift_list, assignee_name=old_name
                ).update(assignee_name=guest_name)
                if updated > 0:
                    GiftAuditLog.objects.create(
                        gift_list=gift_list,
                        action='update_claims',
                        assignee_name=f"{old_name} → {guest_name}",
                        session_id=request.session.session_key or '',
                    )

        return redirect('gift-list', slug=slug)

    def _render_gift_list(self, request, gift_list, guest_name, error=None):
        """Render the gift list page with claims properly attached."""
        items = gift_list.items.all()
        claims = {c.item_id: c for c in GiftClaim.objects.filter(item__in=items)}
        for item in items:
            if item.id in claims:
                item.claim = claims[item.id]
        claimed = sum(1 for i in items if hasattr(i, 'claim') and i.claim is not None)
        return render(request, self.template_name, {
            'gift_list': gift_list,
            'items': items,
            'guest_name': guest_name,
            'total_items': items.count(),
            'claimed_items': claimed,
            'error': error,
        })


def gift_list_view(request, slug):
    view = GiftListView.as_view()
    return view(request, slug=slug)


def gift_index_view(request):
    """List all active gift lists."""
    from django.shortcuts import render
    from core.session import get_guest_name
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
    return render(request, 'gifts/gift_index.html', {
        'guest_name': get_guest_name(request),
        'gift_lists': gift_list_data,
    })


def gift_count_json(request, slug):
    """JSON endpoint returning current claim counts for auto-refresh."""
    from django.http import JsonResponse
    gift_list = get_object_or_404(GiftList, slug=slug)
    items = gift_list.items.all()
    total = items.count()
    claimed = GiftClaim.objects.filter(item__in=items).count()
    return JsonResponse({
        'total': total,
        'claimed': claimed,
    })
