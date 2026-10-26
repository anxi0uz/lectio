from lectio.core.exceptions import (
    AuthenticationError,
    ConflictError,
    PermissionDeniedError,
)


class EmailAlreadyRegisteredError(ConflictError):
    default_detail = "Email already registered"


class InvalidRefreshTokenError(AuthenticationError):
    default_detail = "Invalid or expired refresh token"


class InvalidCredentialsError(AuthenticationError):
    default_detail = "Invalid credentials"


class TeacherRequiredError(PermissionDeniedError):
    default_detail = "Only teachers can do this"
