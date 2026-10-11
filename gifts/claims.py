from django.db import transaction, DatabaseError
from gifts.models import GiftItem, GiftClaim, GiftAuditLog
from gifts.exceptions import ClaimCollisionError, ItemNotFoundError, ClaimNotFoundError


def claim_item(gift_list, item_id, guest_name, session_id):
    """
    Claim an item in a gift list for a guest.

    Acquires a nowait row lock on GiftItem within an atomic transaction.
    Raises ClaimCollisionError if the item is already claimed or if lock acquisition fails.
    Raises ItemNotFoundError if the item does not exist in gift_list.
    Atomically creates GiftClaim and GiftAuditLog.
    """
    with transaction.atomic():
        try:
            item = GiftItem.objects.select_for_update(nowait=True).get(
                id=item_id, gift_list=gift_list
            )
        except GiftItem.DoesNotExist:
            raise ItemNotFoundError(f"GiftItem {item_id} not found in gift list")
        except DatabaseError as e:
            raise ClaimCollisionError(str(e))

        existing_claim = GiftClaim.objects.filter(item=item).first()
        if existing_claim is not None:
            raise ClaimCollisionError(
                f"GiftItem {item_id} is already claimed by {existing_claim.assignee_name}"
            )

        try:
            claim = GiftClaim.objects.create(
                item=item,
                assignee_name=guest_name,
                session_id=session_id or '',
            )
            GiftAuditLog.objects.create(
                gift_list=gift_list,
                item=item,
                action='claim',
                assignee_name=guest_name,
                session_id=session_id or '',
            )
        except DatabaseError as e:
            raise ClaimCollisionError(str(e))

        return claim


def edit_claim(gift_list, claim_id, guest_name, session_id):
    """
    Edit an existing claim's assignee name.

    Acquires a nowait row lock on GiftItem within an atomic transaction.
    Raises ClaimNotFoundError if claim does not exist in gift_list.
    Raises ClaimCollisionError if row locking fails.
    Atomically updates GiftClaim and creates GiftAuditLog.
    """
    with transaction.atomic():
        try:
            claim = (
                GiftClaim.objects.select_for_update(nowait=True)
                .select_related('item')
                .get(id=claim_id, item__gift_list=gift_list)
            )
        except GiftClaim.DoesNotExist:
            raise ClaimNotFoundError(f"GiftClaim {claim_id} not found in gift list")
        except DatabaseError as e:
            raise ClaimCollisionError(str(e))

        item = claim.item
        old_name = claim.assignee_name
        claim.assignee_name = guest_name
        claim.save()

        GiftAuditLog.objects.create(
            gift_list=gift_list,
            item=item,
            action='edit',
            assignee_name=f"{old_name} → {guest_name}",
            session_id=session_id or '',
        )
        return claim


def delete_claim(gift_list, item_id, session_id):
    """
    Delete a claim from an item in a gift list.

    Acquires a nowait row lock on GiftItem within an atomic transaction.
    Raises ItemNotFoundError if item does not exist in gift_list.
    Raises ClaimNotFoundError if no claim exists for the item.
    Raises ClaimCollisionError if row locking fails.
    Atomically removes GiftClaim and creates GiftAuditLog.
    """
    with transaction.atomic():
        try:
            item = GiftItem.objects.select_for_update(nowait=True).get(
                id=item_id, gift_list=gift_list
            )
        except GiftItem.DoesNotExist:
            raise ItemNotFoundError(f"GiftItem {item_id} not found in gift list")
        except DatabaseError as e:
            raise ClaimCollisionError(str(e))

        claim = GiftClaim.objects.filter(item=item).first()
        if not claim:
            raise ClaimNotFoundError(f"No claim found for gift item {item_id}")

        assignee = claim.assignee_name
        claim.delete()

        GiftAuditLog.objects.create(
            gift_list=gift_list,
            item=item,
            action='delete',
            assignee_name=assignee,
            session_id=session_id or '',
            is_deleted=True,
        )


def update_guest_claims(gift_list, old_name, new_name, session_id):
    """
    Update all claims belonging to old_name to new_name within a gift list.

    Acquires nowait row locks on all affected GiftItem rows within an atomic transaction.
    Raises ClaimCollisionError if row locking fails.
    Atomically updates GiftClaim entries and creates a GiftAuditLog entry.
    """
    with transaction.atomic():
        try:
            items = list(
                GiftItem.objects.select_for_update(nowait=True)
                .filter(gift_list=gift_list, claim__assignee_name=old_name)
                .order_by('id')
            )
        except DatabaseError as e:
            raise ClaimCollisionError(str(e))

        if not items or not old_name:
            return 0

        updated = GiftClaim.objects.filter(
            item__gift_list=gift_list, assignee_name=old_name
        ).update(assignee_name=new_name)

        if updated > 0:
            GiftAuditLog.objects.create(
                gift_list=gift_list,
                action='update_claims',
                assignee_name=f"{old_name} → {new_name}",
                session_id=session_id or '',
            )
        return updated

