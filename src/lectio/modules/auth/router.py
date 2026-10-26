from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status
from fastapi.responses import JSONResponse

from lectio.api.dependencies import RedisDep, SessionDep
from lectio.core.config import get_settings
from lectio.modules.auth.dependencies import CurrentUserDep
from lectio.modules.auth.exceptions import InvalidRefreshTokenError
from lectio.modules.auth.rate_limits import (
    enforce_login_rate_limit,
    enforce_register_rate_limit,
)
from lectio.modules.auth.schemas import (
    AccessTokenResponse,
    AuthResponse,
    LoginRequest,
    RegisterRequest,
)
from lectio.modules.auth.service import (
    login,
    logout,
    logout_everywhere,
    refresh_tokens,
    register,
)
from lectio.modules.users.schemas import UserResponse

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)

REFRESH_COOKIE_PATH = "/api/v1/auth"


def _client_ip(request: Request) -> str:
    # Behind a reverse proxy run uvicorn with --proxy-headers and
    # --forwarded-allow-ips so this is the real client address.
    return request.client.host if request.client else "unknown"


def _set_refresh_cookie(
    response: Response,
    refresh_token: str,
) -> None:
    settings = get_settings()

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.refresh_cookie_secure,
        path=REFRESH_COOKIE_PATH,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


def _delete_refresh_cookie(
    response: Response,
) -> None:
    response.delete_cookie(
        key="refresh_token",
        path=REFRESH_COOKIE_PATH,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    request: Request,
    payload: RegisterRequest,
    db: SessionDep,
    redis: RedisDep,
    response: Response,
) -> AuthResponse:
    await enforce_register_rate_limit(redis, _client_ip(request))

    result = await register(db, payload, redis)

    _set_refresh_cookie(response, result.refresh_token)
    return AuthResponse.model_validate(
        {
            "access_token": result.access_token,
            "user": result.user,
        },
    )


@router.post(
    "/login",
    response_model=AuthResponse,
)
async def login_user(
    request: Request,
    payload: LoginRequest,
    db: SessionDep,
    redis: RedisDep,
    response: Response,
) -> AuthResponse:
    await enforce_login_rate_limit(
        redis,
        _client_ip(request),
        str(payload.email),
    )

    result = await login(db, payload, redis)

    _set_refresh_cookie(response, result.refresh_token)
    return AuthResponse.model_validate(
        {
            "access_token": result.access_token,
            "user": result.user,
        },
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
)
async def refresh_access_token(
    response: Response,
    db: SessionDep,
    redis: RedisDep,
    refresh_token: Annotated[
        str | None,
        Cookie(alias="refresh_token"),
    ] = None,
) -> AccessTokenResponse | JSONResponse:
    try:
        if refresh_token is None:
            raise InvalidRefreshTokenError
        result = await refresh_tokens(
            db,
            redis,
            refresh_token,
        )
    except InvalidRefreshTokenError as error:
        # Handled here rather than globally: the stale cookie must be cleared
        # on the error response itself.
        error_response = JSONResponse(
            {"detail": error.detail},
            status_code=error.status_code,
        )
        _delete_refresh_cookie(error_response)
        return error_response

    _set_refresh_cookie(
        response,
        result.refresh_token,
    )

    return AccessTokenResponse(
        access_token=result.access_token,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout_user(
    response: Response,
    redis: RedisDep,
    refresh_token: Annotated[
        str | None,
        Cookie(alias="refresh_token"),
    ] = None,
) -> None:
    await logout(
        redis,
        refresh_token,
    )

    _delete_refresh_cookie(response)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout_all_sessions(
    response: Response,
    redis: RedisDep,
    current_user: CurrentUserDep,
) -> None:
    await logout_everywhere(
        redis,
        current_user.id,
    )

    _delete_refresh_cookie(response)


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: CurrentUserDep,
) -> UserResponse:
    return UserResponse.model_validate(
        current_user,
    )
