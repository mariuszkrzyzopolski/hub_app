import pytest
from core.exceptions import CollisionError, NotFoundError, LockedError, HubDomainError


def test_exception_hierarchy():
    from events.exceptions import (
        RoleCollisionError,
        RoleAlreadyAssignedError,
        CategoryCollisionError,
        CategoryLockedError,
        RoleNotFoundError,
        CategoryNotFoundError,
        AssignmentNotFoundError,
    )
    assert issubclass(RoleCollisionError, CollisionError)
    assert issubclass(RoleCollisionError, HubDomainError)
    assert issubclass(RoleAlreadyAssignedError, RoleCollisionError)
    assert issubclass(CategoryCollisionError, RoleCollisionError)
    assert issubclass(CategoryLockedError, LockedError)
    assert issubclass(CategoryLockedError, HubDomainError)
    assert issubclass(RoleNotFoundError, NotFoundError)
    assert issubclass(RoleNotFoundError, HubDomainError)
    assert issubclass(CategoryNotFoundError, NotFoundError)
    assert issubclass(CategoryNotFoundError, HubDomainError)
    assert issubclass(AssignmentNotFoundError, RoleNotFoundError)
    assert issubclass(AssignmentNotFoundError, NotFoundError)
    assert issubclass(AssignmentNotFoundError, HubDomainError)


@pytest.mark.django_db(transaction=True)
class TestAssignRole:
    def test_assign_role_success(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")

        assignment = assignments.assign_role(event, role.id, "Alice", "session-123")

        assert assignment.role_id == role.id
        assert assignment.assignee_name == "Alice"
        assert assignment.session_id == "session-123"
        assert not assignment.via_category

        db_assignment = RoleAssignment.objects.get(role=role)
        assert db_assignment.assignee_name == "Alice"

        audit = EventAuditLog.objects.get(event=event, role=role)
        assert audit.action == "assign"
        assert audit.assignee_name == "Alice"
        assert audit.session_id == "session-123"

    def test_assign_role_not_found(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import RoleNotFoundError

        event = Event.objects.create(name="Summer Gathering")
        other_event = Event.objects.create(name="Other Gathering")
        cat = RoleCategory.objects.create(event=other_event, name="Music")
        other_role = Role.objects.create(category=cat, name="DJ")

        with pytest.raises(RoleNotFoundError):
            assignments.assign_role(event, 999999, "Alice", "session-123")

        with pytest.raises(RoleNotFoundError):
            assignments.assign_role(event, other_role.id, "Alice", "session-123")

    def test_assign_role_already_assigned_raises_collision(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import RoleCollisionError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")

        assignments.assign_role(event, role.id, "Alice", "session-1")

        with pytest.raises(RoleCollisionError) as exc_info:
            assignments.assign_role(event, role.id, "Bob", "session-2")
        assert "Ta rola jest już przypisana." in str(exc_info.value)

    def test_assign_role_category_locked_raises_category_locked(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment
        from events.exceptions import CategoryLockedError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role1 = Role.objects.create(category=cat, name="DJ")
        role2 = Role.objects.create(category=cat, name="Speaker Setup")

        # Claim category via role1
        RoleAssignment.objects.create(role=role1, assignee_name="Charlie", session_id="s1", via_category=True)

        with pytest.raises(CategoryLockedError) as exc_info:
            assignments.assign_role(event, role2.id, "Alice", "session-2")
        assert "Ta kategoria jest zarezerwowana" in str(exc_info.value)

    def test_assign_role_lock_contention_raises_collision(self):
        import threading
        from django.db import connection, transaction
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import RoleCollisionError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")

        barrier = threading.Barrier(2)
        lock_acquired = threading.Event()

        def hold_lock():
            try:
                connection.close()
                with transaction.atomic():
                    Role.objects.select_for_update().get(id=role.id)
                    lock_acquired.set()
                    barrier.wait(timeout=5)
            finally:
                connection.close()

        t = threading.Thread(target=hold_lock)
        t.start()
        try:
            lock_acquired.wait(timeout=5)
            connection.close()
            with pytest.raises(RoleCollisionError) as exc_info:
                assignments.assign_role(event, role.id, "Alice", "session-123")
            assert "Ta rola została właśnie przypisana" in str(exc_info.value)
        finally:
            barrier.wait(timeout=5)
            t.join(timeout=5)
            connection.close()

    def test_assign_role_rollback_on_failure(self, monkeypatch):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog
        from django.db import DatabaseError
        from events.exceptions import RoleCollisionError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")

        def failing_create(*args, **kwargs):
            raise DatabaseError("Simulated database error during audit logging")

        monkeypatch.setattr(EventAuditLog.objects, "create", failing_create)

        with pytest.raises(RoleCollisionError):
            assignments.assign_role(event, role.id, "Alice", "session-123")

        assert not RoleAssignment.objects.filter(role=role).exists()
        assert not EventAuditLog.objects.filter(event=event).exists()


@pytest.mark.django_db(transaction=True)
class TestAssignCategory:
    def test_assign_category_success(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Food")
        role1 = Role.objects.create(category=cat, name="Grill Master")
        role2 = Role.objects.create(category=cat, name="Salad Maker")

        created = assignments.assign_category(event, cat.id, "Alice", "session-123")
        assert len(created) == 2

        a1 = RoleAssignment.objects.get(role=role1)
        a2 = RoleAssignment.objects.get(role=role2)
        assert a1.assignee_name == "Alice"
        assert a1.via_category is True
        assert a2.assignee_name == "Alice"
        assert a2.via_category is True

        audit = EventAuditLog.objects.get(event=event, action="assign_category")
        assert audit.assignee_name == "Alice"
        assert audit.session_id == "session-123"

    def test_assign_category_skips_individually_assigned(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Food")
        role1 = Role.objects.create(category=cat, name="Grill Master")
        role2 = Role.objects.create(category=cat, name="Salad Maker")

        RoleAssignment.objects.create(role=role1, assignee_name="Bob", session_id="s1", via_category=False)

        created = assignments.assign_category(event, cat.id, "Alice", "session-123")
        assert len(created) == 1
        assert created[0].role_id == role2.id

        assert RoleAssignment.objects.get(role=role1).assignee_name == "Bob"
        assert RoleAssignment.objects.get(role=role2).assignee_name == "Alice"

    def test_assign_category_not_found(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory
        from events.exceptions import CategoryNotFoundError

        event = Event.objects.create(name="Summer Gathering")
        other_event = Event.objects.create(name="Other Gathering")
        cat = RoleCategory.objects.create(event=other_event, name="Food")

        with pytest.raises(CategoryNotFoundError):
            assignments.assign_category(event, 999999, "Alice", "session-123")

        with pytest.raises(CategoryNotFoundError):
            assignments.assign_category(event, cat.id, "Alice", "session-123")

    def test_assign_category_already_claimed_raises_collision(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import RoleCollisionError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Food")
        Role.objects.create(category=cat, name="Grill Master")

        assignments.assign_category(event, cat.id, "Alice", "session-1")

        with pytest.raises(RoleCollisionError) as exc_info:
            assignments.assign_category(event, cat.id, "Bob", "session-2")
        assert "Kategoria została właśnie zajęta" in str(exc_info.value)

    def test_assign_category_lock_contention_raises_collision(self):
        import time
        import threading
        from django.db import connection, transaction
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment
        from events.exceptions import RoleCollisionError, CategoryCollisionError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Food")
        role = Role.objects.create(category=cat, name="Grill Master")

        lock_acquired = threading.Event()

        def hold_lock():
            try:
                connection.close()
                with transaction.atomic():
                    Role.objects.select_for_update().get(id=role.id)
                    lock_acquired.set()
                    time.sleep(0.5)
                    RoleAssignment.objects.create(role=role, assignee_name="Bob", session_id="s1", via_category=True)
            finally:
                connection.close()

        t = threading.Thread(target=hold_lock)
        t.start()
        try:
            lock_acquired.wait(timeout=5)
            connection.close()
            with pytest.raises(RoleCollisionError) as exc_info:
                assignments.assign_category(event, cat.id, "Alice", "session-123")
            assert "Kategoria została właśnie zajęta" in str(exc_info.value)
            assert isinstance(exc_info.value, CategoryCollisionError)
        finally:
            t.join(timeout=5)
            connection.close()

    def test_assign_category_rollback_on_failure(self, monkeypatch):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Food")
        role1 = Role.objects.create(category=cat, name="Grill Master")
        role2 = Role.objects.create(category=cat, name="Salad Maker")

        def failing_create(*args, **kwargs):
            raise RuntimeError("Simulated failure during audit log creation")

        monkeypatch.setattr(EventAuditLog.objects, "create", failing_create)

        with pytest.raises(RuntimeError):
            assignments.assign_category(event, cat.id, "Alice", "session-123")

        assert not RoleAssignment.objects.filter(role__in=[role1, role2]).exists()
        assert not EventAuditLog.objects.filter(event=event).exists()


@pytest.mark.django_db(transaction=True)
class TestUnclaimCategory:
    def test_unclaim_category_success(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Food")
        role1 = Role.objects.create(category=cat, name="Grill Master")
        role2 = Role.objects.create(category=cat, name="Salad Maker")

        RoleAssignment.objects.create(role=role1, assignee_name="Bob", session_id="s1", via_category=False)
        RoleAssignment.objects.create(role=role2, assignee_name="Alice", session_id="s2", via_category=True)

        deleted_count = assignments.unclaim_category(event, cat.id, "Alice", "session-s2")
        assert deleted_count == 1

        # role1 still assigned
        assert RoleAssignment.objects.filter(role=role1).exists()
        # role2 unassigned
        assert not RoleAssignment.objects.filter(role=role2).exists()

        audit = EventAuditLog.objects.get(event=event, action="unclaim_category")
        assert audit.assignee_name == "Alice"

    def test_unclaim_category_not_found(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory
        from events.exceptions import CategoryNotFoundError

        event = Event.objects.create(name="Summer Gathering")
        other_event = Event.objects.create(name="Other Gathering")
        cat = RoleCategory.objects.create(event=other_event, name="Food")

        with pytest.raises(CategoryNotFoundError):
            assignments.unclaim_category(event, 999999, "Alice", "session-123")

        with pytest.raises(CategoryNotFoundError):
            assignments.unclaim_category(event, cat.id, "Alice", "session-123")

    def test_unclaim_category_lock_contention_raises_collision(self):
        import threading
        from django.db import connection, transaction
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import RoleCollisionError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Food")
        role = Role.objects.create(category=cat, name="Grill Master")

        barrier = threading.Barrier(2)
        lock_acquired = threading.Event()

        def hold_lock():
            try:
                connection.close()
                with transaction.atomic():
                    Role.objects.select_for_update().get(id=role.id)
                    lock_acquired.set()
                    barrier.wait(timeout=5)
            finally:
                connection.close()

        t = threading.Thread(target=hold_lock)
        t.start()
        try:
            lock_acquired.wait(timeout=5)
            connection.close()
            with pytest.raises(RoleCollisionError):
                assignments.unclaim_category(event, cat.id, "Alice", "session-123")
        finally:
            barrier.wait(timeout=5)
            t.join(timeout=5)
            connection.close()

    def test_unclaim_category_rollback_on_failure(self, monkeypatch):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Food")
        role1 = Role.objects.create(category=cat, name="Grill Master")
        role2 = Role.objects.create(category=cat, name="Salad Maker")
        RoleAssignment.objects.create(role=role1, assignee_name="Bob", session_id="s1", via_category=False)
        RoleAssignment.objects.create(role=role2, assignee_name="Alice", session_id="s2", via_category=True)

        def failing_create(*args, **kwargs):
            raise RuntimeError("Simulated failure during audit log creation")

        monkeypatch.setattr(EventAuditLog.objects, "create", failing_create)

        with pytest.raises(RuntimeError):
            assignments.unclaim_category(event, cat.id, "Alice", "session-s2")

        assert RoleAssignment.objects.filter(role=role1).exists()
        assert RoleAssignment.objects.filter(role=role2).exists()
        assert not EventAuditLog.objects.filter(event=event, action="unclaim_category").exists()


@pytest.mark.django_db(transaction=True)
class TestEditAssignment:
    def test_edit_assignment_success(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        assignment = assignments.assign_role(event, role.id, "Alice", "session-1")

        updated = assignments.edit_assignment(event, assignment.id, "Bob", "session-2")
        assert updated.assignee_name == "Bob"

        assignment.refresh_from_db()
        assert assignment.assignee_name == "Bob"

        audit = EventAuditLog.objects.get(event=event, action="edit")
        assert audit.assignee_name == "Alice → Bob"
        assert audit.session_id == "session-2"

    def test_edit_assignment_not_found(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import AssignmentNotFoundError

        event = Event.objects.create(name="Summer Gathering")
        other_event = Event.objects.create(name="Other Gathering")
        cat = RoleCategory.objects.create(event=other_event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        other_assignment = assignments.assign_role(other_event, role.id, "Alice", "s1")

        with pytest.raises(AssignmentNotFoundError):
            assignments.edit_assignment(event, 999999, "Bob", "s2")

        with pytest.raises(AssignmentNotFoundError):
            assignments.edit_assignment(event, other_assignment.id, "Bob", "s2")

    def test_edit_assignment_lock_contention_raises_collision(self):
        import threading
        from django.db import connection, transaction
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import RoleCollisionError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        assignment = assignments.assign_role(event, role.id, "Alice", "s1")

        barrier = threading.Barrier(2)
        lock_acquired = threading.Event()

        def hold_lock():
            try:
                connection.close()
                with transaction.atomic():
                    Role.objects.select_for_update().get(id=role.id)
                    lock_acquired.set()
                    barrier.wait(timeout=5)
            finally:
                connection.close()

        t = threading.Thread(target=hold_lock)
        t.start()
        try:
            lock_acquired.wait(timeout=5)
            connection.close()
            with pytest.raises(RoleCollisionError):
                assignments.edit_assignment(event, assignment.id, "Bob", "s2")
        finally:
            barrier.wait(timeout=5)
            t.join(timeout=5)
            connection.close()

    def test_edit_assignment_rollback_on_failure(self, monkeypatch):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        assignment = assignments.assign_role(event, role.id, "Alice", "s1")

        def failing_create(*args, **kwargs):
            raise RuntimeError("Simulated failure during edit audit log creation")

        monkeypatch.setattr(EventAuditLog.objects, "create", failing_create)

        with pytest.raises(RuntimeError):
            assignments.edit_assignment(event, assignment.id, "Bob", "s2")

        assignment.refresh_from_db()
        assert assignment.assignee_name == "Alice"
        assert not EventAuditLog.objects.filter(event=event, action="edit").exists()


@pytest.mark.django_db(transaction=True)
class TestDeleteAssignment:
    def test_delete_assignment_success(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        assignments.assign_role(event, role.id, "Alice", "s1")

        assignments.delete_assignment(event, role.id, "s1")

        assert not RoleAssignment.objects.filter(role=role).exists()

        audit = EventAuditLog.objects.get(event=event, action="delete")
        assert audit.assignee_name == "Alice"
        assert audit.is_deleted is True

    def test_delete_assignment_role_not_found(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import RoleNotFoundError

        event = Event.objects.create(name="Summer Gathering")
        other_event = Event.objects.create(name="Other Gathering")
        cat = RoleCategory.objects.create(event=other_event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")

        with pytest.raises(RoleNotFoundError):
            assignments.delete_assignment(event, 999999, "s1")

        with pytest.raises(RoleNotFoundError):
            assignments.delete_assignment(event, role.id, "s1")

    def test_delete_assignment_assignment_not_found(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import AssignmentNotFoundError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")

        with pytest.raises(AssignmentNotFoundError):
            assignments.delete_assignment(event, role.id, "s1")

    def test_delete_assignment_category_locked_raises_category_locked(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment
        from events.exceptions import CategoryLockedError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        RoleAssignment.objects.create(role=role, assignee_name="Alice", session_id="s1", via_category=True)

        with pytest.raises(CategoryLockedError) as exc_info:
            assignments.delete_assignment(event, role.id, "s1")
        assert "Ta kategoria jest zarezerwowana" in str(exc_info.value)

    def test_delete_assignment_lock_contention_raises_collision(self):
        import threading
        from django.db import connection, transaction
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import RoleCollisionError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        assignments.assign_role(event, role.id, "Alice", "s1")

        barrier = threading.Barrier(2)
        lock_acquired = threading.Event()

        def hold_lock():
            try:
                connection.close()
                with transaction.atomic():
                    Role.objects.select_for_update().get(id=role.id)
                    lock_acquired.set()
                    barrier.wait(timeout=5)
            finally:
                connection.close()

        t = threading.Thread(target=hold_lock)
        t.start()
        try:
            lock_acquired.wait(timeout=5)
            connection.close()
            with pytest.raises(RoleCollisionError):
                assignments.delete_assignment(event, role.id, "s1")
        finally:
            barrier.wait(timeout=5)
            t.join(timeout=5)
            connection.close()

    def test_delete_assignment_rollback_on_failure(self, monkeypatch):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        assignments.assign_role(event, role.id, "Alice", "s1")

        def failing_create(*args, **kwargs):
            raise RuntimeError("Simulated failure during delete audit log creation")

        monkeypatch.setattr(EventAuditLog.objects, "create", failing_create)

        with pytest.raises(RuntimeError):
            assignments.delete_assignment(event, role.id, "s1")

        assert RoleAssignment.objects.filter(role=role).exists()
        assert not EventAuditLog.objects.filter(event=event, action="delete").exists()


@pytest.mark.django_db(transaction=True)
class TestUpdateGuestAssignments:
    def test_update_guest_assignments_success(self):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role1 = Role.objects.create(category=cat, name="DJ")
        role2 = Role.objects.create(category=cat, name="Lights")

        assignments.assign_role(event, role1.id, "Alice", "s1")
        assignments.assign_role(event, role2.id, "Alice", "s1")

        updated = assignments.update_guest_assignments(event, "Alice", "Alicia", "s1")
        assert updated == 2

        assert RoleAssignment.objects.get(role=role1).assignee_name == "Alicia"
        assert RoleAssignment.objects.get(role=role2).assignee_name == "Alicia"

        audit = EventAuditLog.objects.get(event=event, action="update_claims")
        assert audit.assignee_name == "Alice → Alicia"

    def test_update_guest_assignments_empty_or_no_match(self):
        import events.assignments as assignments
        from events.models import Event

        event = Event.objects.create(name="Summer Gathering")

        assert assignments.update_guest_assignments(event, "", "Alicia", "s1") == 0
        assert assignments.update_guest_assignments(event, "Nobody", "Alicia", "s1") == 0

    def test_update_guest_assignments_lock_contention_raises_collision(self):
        import threading
        from django.db import connection, transaction
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role
        from events.exceptions import RoleCollisionError

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        assignments.assign_role(event, role.id, "Alice", "s1")

        barrier = threading.Barrier(2)
        lock_acquired = threading.Event()

        def hold_lock():
            try:
                connection.close()
                with transaction.atomic():
                    Role.objects.select_for_update().get(id=role.id)
                    lock_acquired.set()
                    barrier.wait(timeout=5)
            finally:
                connection.close()

        t = threading.Thread(target=hold_lock)
        t.start()
        try:
            lock_acquired.wait(timeout=5)
            connection.close()
            with pytest.raises(RoleCollisionError):
                assignments.update_guest_assignments(event, "Alice", "Alicia", "s1")
        finally:
            barrier.wait(timeout=5)
            t.join(timeout=5)
            connection.close()

    def test_update_guest_assignments_rollback_on_failure(self, monkeypatch):
        import events.assignments as assignments
        from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        assignments.assign_role(event, role.id, "Alice", "s1")

        def failing_create(*args, **kwargs):
            raise RuntimeError("Simulated failure during bulk update audit log creation")

        monkeypatch.setattr(EventAuditLog.objects, "create", failing_create)

        with pytest.raises(RuntimeError):
            assignments.update_guest_assignments(event, "Alice", "Alicia", "s1")

        assignment = RoleAssignment.objects.get(role=role)
        assert assignment.assignee_name == "Alice"
        assert not EventAuditLog.objects.filter(event=event, action="update_claims").exists()


@pytest.mark.django_db(transaction=True)
class TestEventDetailViewDelegation:
    def test_post_assign_success_redirects(self, client):
        from events.models import Event, RoleCategory, Role, RoleAssignment

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")

        session = client.session
        session['guest_name'] = 'Alice'
        session['authenticated_slugs'] = {event.slug: {'password_version': event.password_version}}
        session.save()

        response = client.post(f"/events/{event.slug}/", {
            "action": "assign",
            "role_id": role.id,
        })
        assert response.status_code == 302
        assert response.url == f"/events/{event.slug}/"
        assert RoleAssignment.objects.filter(role=role, assignee_name="Alice").exists()

    def test_post_assign_collision_renders_error(self, client):
        from events.models import Event, RoleCategory, Role, RoleAssignment

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        RoleAssignment.objects.create(role=role, assignee_name="Bob", session_id="s1")

        session = client.session
        session['guest_name'] = 'Alice'
        session['authenticated_slugs'] = {event.slug: {'password_version': event.password_version}}
        session.save()

        response = client.post(f"/events/{event.slug}/", {
            "action": "assign",
            "role_id": role.id,
        })
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Ta rola jest już przypisana.' in content

    def test_post_assign_category_locked_renders_error(self, client):
        from events.models import Event, RoleCategory, Role, RoleAssignment

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role1 = Role.objects.create(category=cat, name="DJ")
        role2 = Role.objects.create(category=cat, name="Lights")
        RoleAssignment.objects.create(role=role1, assignee_name="Bob", session_id="s1", via_category=True)

        session = client.session
        session['guest_name'] = 'Alice'
        session['authenticated_slugs'] = {event.slug: {'password_version': event.password_version}}
        session.save()

        response = client.post(f"/events/{event.slug}/", {
            "action": "assign",
            "role_id": role2.id,
        })
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Ta kategoria jest zarezerwowana. Aby zmienić role, najpierw zwolnij kategorię.' in content

    def test_post_assign_category_success_redirects(self, client):
        from events.models import Event, RoleCategory, Role, RoleAssignment

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role1 = Role.objects.create(category=cat, name="DJ")
        role2 = Role.objects.create(category=cat, name="Lights")

        session = client.session
        session['guest_name'] = 'Alice'
        session['authenticated_slugs'] = {event.slug: {'password_version': event.password_version}}
        session.save()

        response = client.post(f"/events/{event.slug}/", {
            "action": "assign_category",
            "category_id": cat.id,
        })
        assert response.status_code == 302
        assert RoleAssignment.objects.filter(role=role1, assignee_name="Alice", via_category=True).exists()
        assert RoleAssignment.objects.filter(role=role2, assignee_name="Alice", via_category=True).exists()

    def test_post_assign_category_collision_renders_error(self, client):
        from events.models import Event, RoleCategory, Role, RoleAssignment

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        RoleAssignment.objects.create(role=role, assignee_name="Bob", session_id="s1", via_category=True)

        session = client.session
        session['guest_name'] = 'Alice'
        session['authenticated_slugs'] = {event.slug: {'password_version': event.password_version}}
        session.save()

        response = client.post(f"/events/{event.slug}/", {
            "action": "assign_category",
            "category_id": cat.id,
        })
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Kategoria została właśnie zajęta. Odśwież stronę i spróbuj ponownie.' in content

    def test_post_unclaim_category_success_redirects(self, client):
        from events.models import Event, RoleCategory, Role, RoleAssignment

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        RoleAssignment.objects.create(role=role, assignee_name="Bob", session_id="s1", via_category=True)

        session = client.session
        session['guest_name'] = 'Bob'
        session['authenticated_slugs'] = {event.slug: {'password_version': event.password_version}}
        session.save()

        response = client.post(f"/events/{event.slug}/", {
            "action": "unclaim_category",
            "category_id": cat.id,
        })
        assert response.status_code == 302
        assert not RoleAssignment.objects.filter(role=role).exists()

    def test_post_edit_success_redirects(self, client):
        from events.models import Event, RoleCategory, Role, RoleAssignment

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        assignment = RoleAssignment.objects.create(role=role, assignee_name="Alice", session_id="s1")

        session = client.session
        session['guest_name'] = 'Alicia'
        session['authenticated_slugs'] = {event.slug: {'password_version': event.password_version}}
        session.save()

        response = client.post(f"/events/{event.slug}/", {
            "action": "edit",
            "assignment_id": assignment.id,
        })
        assert response.status_code == 302
        assignment.refresh_from_db()
        assert assignment.assignee_name == 'Alicia'

    def test_post_delete_success_redirects(self, client):
        from events.models import Event, RoleCategory, Role, RoleAssignment

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        RoleAssignment.objects.create(role=role, assignee_name="Alice", session_id="s1")

        session = client.session
        session['guest_name'] = 'Alice'
        session['authenticated_slugs'] = {event.slug: {'password_version': event.password_version}}
        session.save()

        response = client.post(f"/events/{event.slug}/", {
            "action": "delete",
            "role_id": role.id,
        })
        assert response.status_code == 302
        assert not RoleAssignment.objects.filter(role=role).exists()

    def test_post_update_claims_success_redirects(self, client):
        from events.models import Event, RoleCategory, Role, RoleAssignment

        event = Event.objects.create(name="Summer Gathering")
        cat = RoleCategory.objects.create(event=event, name="Music")
        role = Role.objects.create(category=cat, name="DJ")
        assignment = RoleAssignment.objects.create(role=role, assignee_name="Alice", session_id="s1")

        session = client.session
        session['guest_name'] = 'Alicia'
        session['authenticated_slugs'] = {event.slug: {'password_version': event.password_version}}
        session.save()

        response = client.post(f"/events/{event.slug}/", {
            "action": "update_claims",
            "old_name": "Alice",
        })
        assert response.status_code == 302
        assignment.refresh_from_db()
        assert assignment.assignee_name == 'Alicia'

    def test_post_not_found_raises_404(self, client):
        from events.models import Event

        event = Event.objects.create(name="Summer Gathering")

        session = client.session
        session['guest_name'] = 'Alice'
        session['authenticated_slugs'] = {event.slug: {'password_version': event.password_version}}
        session.save()

        response = client.post(f"/events/{event.slug}/", {
            "action": "assign",
            "role_id": 999999,
        })
        assert response.status_code == 404




