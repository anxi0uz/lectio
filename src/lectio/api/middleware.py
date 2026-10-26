from time import perf_counter
from uuid import uuid4

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.contextvars import bind_contextvars, clear_contextvars

log = structlog.get_logger(
    component="http",
)

IGNORED_PATHS = frozenset(
    {
        "/health",
    }
)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        clear_contextvars()

        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id")

        if not request_id or len(request_id) > 128:
            request_id = uuid4().hex

        bind_contextvars(
            request_id=request_id,
        )

        method = scope["method"]
        path = scope["path"]
        status_code = 500
        started_at = perf_counter()

        async def send_with_request_id(
            message: Message,
        ) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]

                response_headers = MutableHeaders(
                    scope=message,
                )
                response_headers["X-Request-ID"] = str(request_id)
            await send(message)

        try:
            await self.app(
                scope,
                receive,
                send_with_request_id,
            )
        except Exception:
            log.exception(
                "unhandled_request_error",
                method=method,
                path=path,
            )
            raise
        finally:
            duration_ms = round(
                (perf_counter() - started_at) * 1000,
                2,
            )
            if path not in IGNORED_PATHS:
                fields = {
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }

                if status_code >= 500:
                    log.error("http_request", **fields)
                elif status_code >= 400:
                    log.warning("http_request", **fields)
                else:
                    log.info("http_request", **fields)

            clear_contextvars()
