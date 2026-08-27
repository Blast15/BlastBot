from __future__ import annotations


class BotError(Exception):
    """Base error with an optional safe user-facing message."""

    def __init__(self, message: str, user_message: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message or message


class UserFacingError(BotError):
    """An expected failure safe to show to a Discord user."""


class ValidationError(UserFacingError):
    """Input or boundary validation failed."""


class PermissionDeniedError(UserFacingError):
    """The caller is not allowed to perform an operation."""


class ResourceNotFoundError(UserFacingError):
    """A requested application resource does not exist."""


class ConflictError(UserFacingError):
    """The operation conflicts with current persistent state."""


class ExternalServiceError(BotError):
    """An external service failed or returned invalid data."""


class InfrastructureError(BotError):
    """A database, filesystem, or other infrastructure operation failed."""
