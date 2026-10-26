from collections.abc import Mapping
from typing import ClassVar

from fastapi import status


class DomainError(Exception):
    """Base for business errors; the API layer maps them to HTTP responses."""

    status_code: ClassVar[int] = status.HTTP_400_BAD_REQUEST
    default_detail: ClassVar[str] = "Bad request"

    def __init__(
        self,
        detail: str | None = None,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.detail = detail or self.default_detail
        self.headers = dict(headers or {})
        super().__init__(self.detail)


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Not found"


class PermissionDeniedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Permission denied"


class AuthenticationError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Authentication failed"


class RateLimitExceededError(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many requests"

    def __init__(self, retry_after: int) -> None:
        super().__init__(
            headers={"Retry-After": str(retry_after)},
        )


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict"


class ServiceUnavailableError(DomainError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service unavailable"
