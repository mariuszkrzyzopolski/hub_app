from core.exceptions import CollisionError, NotFoundError, LockedError


class RoleCollisionError(CollisionError):
    """Raised when a role is already assigned or when lock contention occurs."""
    pass


class RoleAlreadyAssignedError(RoleCollisionError):
    """Raised when a role is already assigned prior to this operation."""
    pass


class CategoryCollisionError(RoleCollisionError):
    """Raised when category assignment collides or experiences lock contention."""
    pass


class CategoryLockedError(LockedError):
    """Raised when an operation cannot be performed because the category is locked."""
    pass


class RoleNotFoundError(NotFoundError):
    """Raised when a role is not found in the given event."""
    pass


class CategoryNotFoundError(NotFoundError):
    """Raised when a category is not found in the given event."""
    pass


class AssignmentNotFoundError(RoleNotFoundError):
    """Raised when a role assignment is not found in the given event."""
    pass


