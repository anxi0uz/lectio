from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from structlog.contextvars import bind_contextvars

from lectio.api.dependencies import SessionDep
from lectio.models import User
from lectio.models.enums import UserRole
from lectio.modules.auth.exceptions import TeacherRequiredError
from lectio.modules.auth.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: SessionDep,
) -> User | None:
    """The signed-in user, or None for anonymous requests.

    A token that is present but invalid is still rejected: silently treating
    it as anonymous would hide an expired session from the client.
    """
    if credentials is None:
        return None

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as error:
        raise _unauthorized("Invalid or expired token") from error

    user = await db.get(User, user_id)

    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")

    bind_contextvars(
        user_id=str(user.id),
    )

    return user


async def get_current_user(
    user: Annotated[
        User | None,
        Depends(get_optional_user),
    ],
) -> User:
    if user is None:
        raise _unauthorized("Not authenticated")

    return user


async def get_current_teacher(
    user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> User:
    if user.role != UserRole.TEACHER:
        raise TeacherRequiredError

    return user


OptionalUserDep = Annotated[
    User | None,
    Depends(get_optional_user),
]

CurrentUserDep = Annotated[
    User,
    Depends(get_current_user),
]

TeacherDep = Annotated[
    User,
    Depends(get_current_teacher),
]
