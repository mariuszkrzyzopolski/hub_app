import threading
import pytest
from django.db import connection, transaction, DatabaseError
from gifts.models import GiftList, GiftItem, GiftClaim, GiftAuditLog
from gifts.exceptions import ClaimCollisionError, ItemNotFoundError, ClaimNotFoundError
from core.exceptions import CollisionError, NotFoundError, HubDomainError
import gifts.claims as claims


def test_exception_hierarchy():
    assert issubclass(ClaimCollisionError, CollisionError)
    assert issubclass(ClaimCollisionError, HubDomainError)
    assert issubclass(ItemNotFoundError, NotFoundError)
    assert issubclass(ItemNotFoundError, HubDomainError)
    assert issubclass(ClaimNotFoundError, NotFoundError)
    assert issubclass(ClaimNotFoundError, HubDomainError)


@pytest.mark.django_db(transaction=True)
class TestClaimItem:
    def test_claim_item_success(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")

        claim = claims.claim_item(gift_list, item.id, "Alice", "session-123")

        assert claim.item_id == item.id
        assert claim.assignee_name == "Alice"
        assert claim.session_id == "session-123"

        db_claim = GiftClaim.objects.get(item=item)
        assert db_claim.assignee_name == "Alice"

        audit = GiftAuditLog.objects.get(gift_list=gift_list, item=item)
        assert audit.action == "claim"
        assert audit.assignee_name == "Alice"
        assert audit.session_id == "session-123"

    def test_claim_item_item_not_found(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        other_list = GiftList.objects.create(name="Other List")
        item = GiftItem.objects.create(gift_list=other_list, name="Lego Set")

        with pytest.raises(ItemNotFoundError):
            claims.claim_item(gift_list, 999999, "Alice", "session-123")

        with pytest.raises(ItemNotFoundError):
            claims.claim_item(gift_list, item.id, "Alice", "session-123")

    def test_claim_item_already_claimed_raises_collision(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claims.claim_item(gift_list, item.id, "Alice", "session-1")

        with pytest.raises(ClaimCollisionError):
            claims.claim_item(gift_list, item.id, "Bob", "session-2")

    def test_claim_item_locked_row_raises_collision(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")

        barrier = threading.Barrier(2)
        lock_acquired = threading.Event()

        def hold_lock():
            try:
                connection.close()
                with transaction.atomic():
                    GiftItem.objects.select_for_update().get(id=item.id)
                    lock_acquired.set()
                    barrier.wait(timeout=5)
            finally:
                connection.close()

        t = threading.Thread(target=hold_lock)
        t.start()
        try:
            lock_acquired.wait(timeout=5)
            connection.close()
            with pytest.raises(ClaimCollisionError):
                claims.claim_item(gift_list, item.id, "Alice", "session-123")
        finally:
            barrier.wait(timeout=5)
            t.join(timeout=5)
            connection.close()

    def test_claim_item_rollback_on_failure(self, monkeypatch):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")

        def failing_create(*args, **kwargs):
            raise DatabaseError("Simulated database failure during audit log creation")

        monkeypatch.setattr(GiftAuditLog.objects, "create", failing_create)

        with pytest.raises(ClaimCollisionError):
            claims.claim_item(gift_list, item.id, "Alice", "session-123")

        assert not GiftClaim.objects.filter(item=item).exists()
        assert not GiftAuditLog.objects.filter(item=item).exists()


@pytest.mark.django_db(transaction=True)
class TestEditClaim:
    def test_edit_claim_success(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claim = claims.claim_item(gift_list, item.id, "Alice", "session-1")

        updated_claim = claims.edit_claim(gift_list, claim.id, "Bob", "session-2")

        assert updated_claim.assignee_name == "Bob"
        claim.refresh_from_db()
        assert claim.assignee_name == "Bob"

        audit = GiftAuditLog.objects.filter(gift_list=gift_list, item=item, action="edit").first()
        assert audit is not None
        assert audit.assignee_name == "Alice → Bob"
        assert audit.session_id == "session-2"

    def test_edit_claim_not_found(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        other_list = GiftList.objects.create(name="Other List")
        item = GiftItem.objects.create(gift_list=other_list, name="Lego Set")
        other_claim = claims.claim_item(other_list, item.id, "Alice", "session-1")

        with pytest.raises(ClaimNotFoundError):
            claims.edit_claim(gift_list, 999999, "Bob", "session-2")

        with pytest.raises(ClaimNotFoundError):
            claims.edit_claim(gift_list, other_claim.id, "Bob", "session-2")

    def test_edit_claim_locked_row_raises_collision(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claim = claims.claim_item(gift_list, item.id, "Alice", "session-1")

        barrier = threading.Barrier(2)
        lock_acquired = threading.Event()

        def hold_lock():
            try:
                connection.close()
                with transaction.atomic():
                    GiftItem.objects.select_for_update().get(id=item.id)
                    lock_acquired.set()
                    barrier.wait(timeout=5)
            finally:
                connection.close()

        t = threading.Thread(target=hold_lock)
        t.start()
        try:
            lock_acquired.wait(timeout=5)
            connection.close()
            with pytest.raises(ClaimCollisionError):
                claims.edit_claim(gift_list, claim.id, "Bob", "session-2")
        finally:
            barrier.wait(timeout=5)
            t.join(timeout=5)
            connection.close()

    def test_edit_claim_rollback_on_failure(self, monkeypatch):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claim = claims.claim_item(gift_list, item.id, "Alice", "session-1")

        def failing_create(*args, **kwargs):
            raise RuntimeError("Simulated failure during edit audit log creation")

        monkeypatch.setattr(GiftAuditLog.objects, "create", failing_create)

        with pytest.raises(RuntimeError):
            claims.edit_claim(gift_list, claim.id, "Bob", "session-2")

        claim.refresh_from_db()
        assert claim.assignee_name == "Alice"
        assert GiftAuditLog.objects.filter(gift_list=gift_list, item=item, action="edit").count() == 0


@pytest.mark.django_db(transaction=True)
class TestDeleteClaim:
    def test_delete_claim_success(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claims.claim_item(gift_list, item.id, "Alice", "session-1")

        claims.delete_claim(gift_list, item.id, "session-1")

        assert not GiftClaim.objects.filter(item=item).exists()

        audit = GiftAuditLog.objects.filter(gift_list=gift_list, item=item, action="delete").first()
        assert audit is not None
        assert audit.assignee_name == "Alice"
        assert audit.is_deleted is True

    def test_delete_claim_item_not_found(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        other_list = GiftList.objects.create(name="Other List")
        item = GiftItem.objects.create(gift_list=other_list, name="Lego Set")

        with pytest.raises(ItemNotFoundError):
            claims.delete_claim(gift_list, 999999, "session-1")

        with pytest.raises(ItemNotFoundError):
            claims.delete_claim(gift_list, item.id, "session-1")

    def test_delete_claim_claim_not_found(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")

        with pytest.raises(ClaimNotFoundError):
            claims.delete_claim(gift_list, item.id, "session-1")

    def test_delete_claim_locked_row_raises_collision(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claims.claim_item(gift_list, item.id, "Alice", "session-1")

        barrier = threading.Barrier(2)
        lock_acquired = threading.Event()

        def hold_lock():
            try:
                connection.close()
                with transaction.atomic():
                    GiftItem.objects.select_for_update().get(id=item.id)
                    lock_acquired.set()
                    barrier.wait(timeout=5)
            finally:
                connection.close()

        t = threading.Thread(target=hold_lock)
        t.start()
        try:
            lock_acquired.wait(timeout=5)
            connection.close()
            with pytest.raises(ClaimCollisionError):
                claims.delete_claim(gift_list, item.id, "session-1")
        finally:
            barrier.wait(timeout=5)
            t.join(timeout=5)
            connection.close()

    def test_delete_claim_rollback_on_failure(self, monkeypatch):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claims.claim_item(gift_list, item.id, "Alice", "session-1")

        def failing_create(*args, **kwargs):
            raise RuntimeError("Simulated failure during delete audit log creation")

        monkeypatch.setattr(GiftAuditLog.objects, "create", failing_create)

        with pytest.raises(RuntimeError):
            claims.delete_claim(gift_list, item.id, "session-1")

        assert GiftClaim.objects.filter(item=item).exists()
        assert GiftAuditLog.objects.filter(gift_list=gift_list, item=item, action="delete").count() == 0


@pytest.mark.django_db(transaction=True)
class TestUpdateGuestClaims:
    def test_update_guest_claims_success(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item1 = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        item2 = GiftItem.objects.create(gift_list=gift_list, name="Board Game")
        item3 = GiftItem.objects.create(gift_list=gift_list, name="Book")

        claims.claim_item(gift_list, item1.id, "Alice", "session-1")
        claims.claim_item(gift_list, item2.id, "Alice", "session-1")
        claims.claim_item(gift_list, item3.id, "Bob", "session-2")

        count = claims.update_guest_claims(gift_list, "Alice", "Alicia", "session-1")
        assert count == 2

        claim1 = GiftClaim.objects.get(item=item1)
        claim2 = GiftClaim.objects.get(item=item2)
        claim3 = GiftClaim.objects.get(item=item3)

        assert claim1.assignee_name == "Alicia"
        assert claim2.assignee_name == "Alicia"
        assert claim3.assignee_name == "Bob"

        audit = GiftAuditLog.objects.filter(gift_list=gift_list, action="update_claims").first()
        assert audit is not None
        assert audit.assignee_name == "Alice → Alicia"
        assert audit.session_id == "session-1"

    def test_update_guest_claims_no_match(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claims.claim_item(gift_list, item.id, "Alice", "session-1")

        count = claims.update_guest_claims(gift_list, "Charlie", "Alicia", "session-1")
        assert count == 0
        assert not GiftAuditLog.objects.filter(gift_list=gift_list, action="update_claims").exists()

    def test_update_guest_claims_empty_old_name(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        count = claims.update_guest_claims(gift_list, "", "Alicia", "session-1")
        assert count == 0

    def test_update_guest_claims_locked_row_raises_collision(self):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claims.claim_item(gift_list, item.id, "Alice", "session-1")

        barrier = threading.Barrier(2)
        lock_acquired = threading.Event()

        def hold_lock():
            try:
                connection.close()
                with transaction.atomic():
                    GiftItem.objects.select_for_update().get(id=item.id)
                    lock_acquired.set()
                    barrier.wait(timeout=5)
            finally:
                connection.close()

        t = threading.Thread(target=hold_lock)
        t.start()
        try:
            lock_acquired.wait(timeout=5)
            connection.close()
            with pytest.raises(ClaimCollisionError):
                claims.update_guest_claims(gift_list, "Alice", "Alicia", "session-1")
        finally:
            barrier.wait(timeout=5)
            t.join(timeout=5)
            connection.close()

    def test_update_guest_claims_rollback_on_failure(self, monkeypatch):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claim = claims.claim_item(gift_list, item.id, "Alice", "session-1")

        def failing_create(*args, **kwargs):
            raise RuntimeError("Simulated failure during bulk update audit log creation")

        monkeypatch.setattr(GiftAuditLog.objects, "create", failing_create)

        with pytest.raises(RuntimeError):
            claims.update_guest_claims(gift_list, "Alice", "Alicia", "session-1")

        claim.refresh_from_db()
        assert claim.assignee_name == "Alice"
        assert GiftAuditLog.objects.filter(gift_list=gift_list, action="update_claims").count() == 0


@pytest.mark.django_db
class TestGiftListViewDelegation:
    def test_post_claim_success_redirects(self, client):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")

        session = client.session
        session['guest_name'] = 'Alice'
        session['authenticated_slugs'] = {gift_list.slug: {'password_version': gift_list.password_version}}
        session.save()

        response = client.post(f"/gifts/{gift_list.slug}/", {
            "action": "claim",
            "item_id": item.id,
        })
        assert response.status_code == 302
        assert response.url == f"/gifts/{gift_list.slug}/"
        assert GiftClaim.objects.filter(item=item, assignee_name="Alice").exists()

    def test_post_claim_collision_renders_error(self, client):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        GiftClaim.objects.create(item=item, assignee_name="Bob", session_id="sess-bob")

        session = client.session
        session['guest_name'] = 'Alice'
        session['authenticated_slugs'] = {gift_list.slug: {'password_version': gift_list.password_version}}
        session.save()

        response = client.post(f"/gifts/{gift_list.slug}/", {
            "action": "claim",
            "item_id": item.id,
        })
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Ten prezent został właśnie zajęty. Odśwież stronę i wybierz inny.' in content

    def test_post_edit_claim_success(self, client):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claim = GiftClaim.objects.create(item=item, assignee_name="Alice", session_id="sess-alice")

        session = client.session
        session['guest_name'] = 'Alicia'
        session['authenticated_slugs'] = {gift_list.slug: {'password_version': gift_list.password_version}}
        session.save()

        response = client.post(f"/gifts/{gift_list.slug}/", {
            "action": "edit",
            "claim_id": claim.id,
        })
        assert response.status_code == 302
        claim.refresh_from_db()
        assert claim.assignee_name == "Alicia"

    def test_post_delete_claim_success(self, client):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        GiftClaim.objects.create(item=item, assignee_name="Alice", session_id="sess-alice")

        session = client.session
        session['guest_name'] = 'Alice'
        session['authenticated_slugs'] = {gift_list.slug: {'password_version': gift_list.password_version}}
        session.save()

        response = client.post(f"/gifts/{gift_list.slug}/", {
            "action": "delete",
            "item_id": item.id,
        })
        assert response.status_code == 302
        assert not GiftClaim.objects.filter(item=item).exists()

    def test_post_update_claims_success(self, client):
        gift_list = GiftList.objects.create(name="Birthday List")
        item = GiftItem.objects.create(gift_list=gift_list, name="Lego Set")
        claim = GiftClaim.objects.create(item=item, assignee_name="Alice", session_id="sess-alice")

        session = client.session
        session['guest_name'] = 'Alicia'
        session['authenticated_slugs'] = {gift_list.slug: {'password_version': gift_list.password_version}}
        session.save()

        response = client.post(f"/gifts/{gift_list.slug}/", {
            "action": "update_claims",
            "old_name": "Alice",
        })
        assert response.status_code == 302
        claim.refresh_from_db()
        assert claim.assignee_name == "Alicia"
