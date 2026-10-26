from fastapi import status

from lectio.core.exceptions import DomainError, NotFoundError


class UserNotFoundError(NotFoundError):
    default_detail = "User not found"


class AvatarNotFoundError(NotFoundError):
    default_detail = "User has no avatar"


class InvalidAvatarError(DomainError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = "Avatar must be a PNG, JPEG or WebP image"


class AvatarTooLargeError(DomainError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    default_detail = "Avatar is too large"
