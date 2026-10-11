class HubDomainError(Exception):
    """Base domain exception for personal-hub application."""
    pass


class CollisionError(HubDomainError):
    """Raised when a concurrency conflict or collision occurs."""
    pass


class NotFoundError(HubDomainError):
    """Raised when a requested domain entity is not found."""
    pass


class LockedError(HubDomainError):
    """Raised when an action is blocked because the resource or parent entity is locked."""
    pass

