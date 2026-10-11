from core.exceptions import CollisionError, NotFoundError


class ClaimCollisionError(CollisionError):
    """Raised when a gift item is already claimed or locked by another transaction."""
    pass


class ItemNotFoundError(NotFoundError):
    """Raised when a gift item is not found in the given gift list."""
    pass


class ClaimNotFoundError(NotFoundError):
    """Raised when a gift claim is not found."""
    pass

