from django.db import transaction, DatabaseError
from events.models import Event, RoleCategory, Role, RoleAssignment, EventAuditLog
from events.exceptions import (
    RoleCollisionError,
    RoleAlreadyAssignedError,
    CategoryCollisionError,
    CategoryLockedError,
    RoleNotFoundError,
    CategoryNotFoundError,
    AssignmentNotFoundError,
)


def assign_role(event, role_id, guest_name, session_id):
    """
    Assign a single role to a guest.

    Acquires a nowait row lock on Role within an atomic transaction.
    Raises RoleNotFoundError if role does not exist in event.
    Raises RoleCollisionError if role is already assigned or on lock contention.
    Raises CategoryLockedError if the category is locked by a whole-category claim.
    Atomically creates RoleAssignment and EventAuditLog.
    """
    with transaction.atomic():
        try:
            role = Role.objects.select_for_update(nowait=True).get(
                id=role_id, category__event=event
            )
        except Role.DoesNotExist:
            raise RoleNotFoundError(f"Role {role_id} not found in event")
        except DatabaseError as e:
            raise RoleCollisionError("Ta rola została właśnie przypisana. Odśwież stronę i spróbuj ponownie.")

        existing_assignment = RoleAssignment.objects.filter(role=role).first()
        if existing_assignment is not None:
            raise RoleAlreadyAssignedError("Ta rola jest już przypisana.")

        if role.is_locked:
            raise CategoryLockedError("Ta kategoria jest zarezerwowana. Aby zmienić role, najpierw zwolnij kategorię.")

        try:
            assignment = RoleAssignment.objects.create(
                role=role,
                assignee_name=guest_name,
                session_id=session_id or '',
            )
            EventAuditLog.objects.create(
                event=event,
                role=role,
                action='assign',
                assignee_name=guest_name,
                session_id=session_id or '',
            )
        except DatabaseError as e:
            raise RoleCollisionError("Ta rola została właśnie przypisana. Odśwież stronę i spróbuj ponownie.")

        return assignment


def assign_category(event, category_id, guest_name, session_id):
    """
    Assign all unassigned roles in a category to a guest (whole category claim).

    Acquires ordered nowait row locks on all roles in the category using order_by('id').
    Raises CategoryNotFoundError if category does not exist in event.
    Raises RoleCollisionError if category is already claimed or on lock contention.
    Atomically creates RoleAssignment records with via_category=True and EventAuditLog.
    """
    with transaction.atomic():
        try:
            category = RoleCategory.objects.get(id=category_id, event=event)
        except RoleCategory.DoesNotExist:
            raise CategoryNotFoundError(f"Category {category_id} not found in event")

        try:
            roles = list(
                Role.objects.filter(category=category)
                .select_for_update()
                .order_by('id')
            )
        except DatabaseError as e:
            raise CategoryCollisionError("Kategoria została właśnie zajęta. Odśwież stronę i spróbuj ponownie.")

        # Invariant: check if the category is already claimed via category
        if RoleAssignment.objects.filter(role__in=roles, via_category=True).exists():
            raise CategoryCollisionError("Kategoria została właśnie zajęta. Odśwież stronę i spróbuj ponownie.")

        existing_assignments = {
            a.role_id: a for a in RoleAssignment.objects.filter(role__in=roles)
        }

        created_assignments = []
        for role in roles:
            if role.id not in existing_assignments:
                assignment = RoleAssignment.objects.create(
                    role=role,
                    assignee_name=guest_name,
                    session_id=session_id or '',
                    via_category=True,
                )
                created_assignments.append(assignment)

        EventAuditLog.objects.create(
            event=event,
            action='assign_category',
            assignee_name=guest_name,
            session_id=session_id or '',
        )
        return created_assignments


def unclaim_category(event, category_id, guest_name, session_id):
    """
    Release a whole category claim for all roles assigned via category.

    Acquires ordered row locks on category roles and assignments via order_by('id').
    Raises CategoryNotFoundError if category does not exist in event.
    Raises RoleCollisionError on lock contention.
    Atomically removes via_category assignments and creates EventAuditLog.
    """
    with transaction.atomic():
        try:
            category = RoleCategory.objects.get(id=category_id, event=event)
        except RoleCategory.DoesNotExist:
            raise CategoryNotFoundError(f"Category {category_id} not found in event")

        try:
            # Ordered locks on roles in category
            list(
                Role.objects.filter(category=category)
                .select_for_update(nowait=True)
                .order_by('id')
            )
            assignments = list(
                RoleAssignment.objects.filter(role__category=category, via_category=True)
                .select_for_update(nowait=True)
                .order_by('id')
            )
        except DatabaseError as e:
            raise RoleCollisionError(str(e))

        deleted_count = len(assignments)
        for assignment in assignments:
            assignment.delete()

        EventAuditLog.objects.create(
            event=event,
            action='unclaim_category',
            assignee_name=guest_name,
            session_id=session_id or '',
        )
        return deleted_count


def edit_assignment(event, assignment_id, guest_name, session_id):
    """
    Edit an existing role assignment's assignee name.

    Acquires a nowait row lock on the assigned Role within an atomic transaction.
    Raises AssignmentNotFoundError if assignment does not exist in event.
    Raises RoleCollisionError on lock contention.
    Atomically updates RoleAssignment and creates EventAuditLog.
    """
    with transaction.atomic():
        try:
            assignment = (
                RoleAssignment.objects.select_for_update(nowait=True)
                .select_related('role__category')
                .get(id=assignment_id, role__category__event=event)
            )
        except RoleAssignment.DoesNotExist:
            raise AssignmentNotFoundError(f"RoleAssignment {assignment_id} not found in event")
        except DatabaseError as e:
            raise RoleCollisionError(str(e))

        role = assignment.role
        old_name = assignment.assignee_name
        assignment.assignee_name = guest_name
        assignment.save()

        EventAuditLog.objects.create(
            event=event,
            role=role,
            action='edit',
            assignee_name=f"{old_name} → {guest_name}",
            session_id=session_id or '',
        )
        return assignment


def delete_assignment(event, role_id, session_id):
    """
    Delete a role assignment for a role in an event.

    Acquires a nowait row lock on Role within an atomic transaction.
    Raises RoleNotFoundError if role does not exist in event.
    Raises AssignmentNotFoundError if no assignment exists on the role.
    Raises CategoryLockedError if the role's category is locked or via_category is True.
    Raises RoleCollisionError on lock contention.
    Atomically removes RoleAssignment and creates EventAuditLog with is_deleted=True.
    """
    with transaction.atomic():
        try:
            role = Role.objects.select_for_update(nowait=True).get(
                id=role_id, category__event=event
            )
        except Role.DoesNotExist:
            raise RoleNotFoundError(f"Role {role_id} not found in event")
        except DatabaseError as e:
            raise RoleCollisionError(str(e))

        assignment = RoleAssignment.objects.filter(role=role).first()
        if not assignment:
            raise AssignmentNotFoundError(f"No assignment found for role {role_id}")

        if role.is_locked or role.category.is_claimed or assignment.via_category:
            raise CategoryLockedError("Ta kategoria jest zarezerwowana. Aby zmienić role, najpierw zwolnij kategorię.")

        assignee = assignment.assignee_name
        assignment.delete()

        EventAuditLog.objects.create(
            event=event,
            role=role,
            action='delete',
            assignee_name=assignee,
            session_id=session_id or '',
            is_deleted=True,
        )


def update_guest_assignments(event, old_name, new_name, session_id):
    """
    Update all assignments belonging to old_name to new_name within an event.

    Acquires nowait row locks on all affected Role rows within an atomic transaction
    using consistent order_by('id') ordering.
    Raises RoleCollisionError on lock contention.
    Atomically updates RoleAssignment records and creates EventAuditLog.
    """
    with transaction.atomic():
        if not old_name:
            return 0

        try:
            roles = list(
                Role.objects.select_for_update(nowait=True)
                .filter(category__event=event, assignment__assignee_name=old_name)
                .order_by('id')
            )
        except DatabaseError as e:
            raise RoleCollisionError(str(e))

        if not roles:
            return 0

        updated = RoleAssignment.objects.filter(
            role__category__event=event, assignee_name=old_name
        ).update(assignee_name=new_name)

        if updated > 0:
            EventAuditLog.objects.create(
                event=event,
                action='update_claims',
                assignee_name=f"{old_name} → {new_name}",
                session_id=session_id or '',
            )
        return updated


