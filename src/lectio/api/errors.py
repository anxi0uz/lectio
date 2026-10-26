from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from lectio.core.exceptions import DomainError


async def domain_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    assert isinstance(error, DomainError)

    body: dict[str, str] = {"detail": error.detail}

    if error.code is not None:
        body["code"] = error.code

    return JSONResponse(
        body,
        status_code=error.status_code,
        headers=error.headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
