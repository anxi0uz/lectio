from dataclasses import dataclass
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lectio.models import User
from lectio.modules.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from lectio.modules.auth.refresh_session import (
    consume_refresh_session,
    create_refresh_session,
    revoke_all_refresh_sessions,
    revoke_refresh_session,
)
from lectio.modules.auth.schemas import LoginRequest, RegisterRequest
from lectio.modules.auth.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    verify_password,
)

log = structlog.get_logger(
    component="auth.service",
)


@dataclass(slots=True)
class AuthResult:
    user: User
    access_token: str
    refresh_token: str


@dataclass(slots=True)
class RefreshResult:
    access_token: str
    refresh_token: str


async def register(
    db: AsyncSession,
    data: RegisterRequest,
    redis: Redis,
) -> AuthResult:
    email = str(data.email).lower()
    stmt = select(User).where(User.email == email)
    existing_user = await db.scalar(stmt)

    if existing_user is not None:
        raise EmailAlreadyRegisteredError

    user = User(
        email=email,
        password_hash=await hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=data.role,
    )

    db.add(user)
    try:
        await db.flush()
    except IntegrityError as error:
        raise EmailAlreadyRegisteredError from error

    await db.refresh(user)

    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_session(
        redis,
        user.id,
    )

    log.info(
        "user_registered",
        user_id=str(user.id),
        role=user.role.value,
    )
    return AuthResult(
        user=user,
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def login(
    db: AsyncSession,
    data: LoginRequest,
    redis: Redis,
) -> AuthResult:
    email = str(data.email).lower()

    user = await db.scalar(
        select(User).where(User.email == email),
    )
    if user is None:
        await burn_password_check(data.password)
        log.warning(
            "login_failed",
            reason="unknown_email",
        )
        raise InvalidCredentialsError

    password_is_valid = await verify_password(
        data.password,
        user.password_hash,
    )
    if not password_is_valid or not user.is_active:
        log.warning(
            "login_failed",
            reason="invalid_password" if not password_is_valid else "inactive_user",
            user_id=str(user.id),
        )
        raise InvalidCredentialsError

    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_session(
        redis,
        user.id,
    )

    log.info(
        "user_logged_in",
        user_id=str(user.id),
    )
    return AuthResult(
        user=user,
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def refresh_tokens(
    db: AsyncSession,
    redis: Redis,
    refresh_token: str,
) -> RefreshResult:
    user_id = await consume_refresh_session(
        redis,
        refresh_token,
    )

    user = await db.get(User, user_id)

    if user is None or not user.is_active:
        raise InvalidRefreshTokenError

    access_token = create_access_token(user.id)
    new_refresh_token = await create_refresh_session(
        redis,
        user.id,
    )

    log.info("refresh_token_rotated", user_id=str(user.id))

    return RefreshResult(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


async def logout(
    redis: Redis,
    refresh_token: str | None,
) -> None:
    if refresh_token is not None:
        await revoke_refresh_session(
            redis,
            refresh_token,
        )

    log.info(
        "user_logged_out",
        had_refresh_token=refresh_token is not None,
    )


async def logout_everywhere(
    redis: Redis,
    user_id: UUID,
) -> None:
    revoked = await revoke_all_refresh_sessions(
        redis,
        user_id,
    )

    log.info(
        "user_logged_out_everywhere",
        user_id=str(user_id),
        revoked_sessions=revoked,
    )
