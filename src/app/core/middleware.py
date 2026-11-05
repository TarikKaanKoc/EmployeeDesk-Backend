"""Edge hygiene every response should carry and every request should pass.

Pure ASGI middleware, not `BaseHTTPMiddleware`: the latter buffers
streaming responses and would break the assistant's SSE stream.
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.app.core.config import settings

_API_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-site",
    "Cache-Control": "no-store",
}
_DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: "
    "https://fastapi.tiangolo.com; frame-ancestors 'none'"
)
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_docs = scope.get("path", "").startswith(_DOCS_PATHS)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {k.lower() for k, _ in headers}
                extra = dict(_API_HEADERS)
                if is_docs:
                    extra["Content-Security-Policy"] = _DOCS_CSP
                    extra.pop("Cache-Control", None)
                if not settings.DEBUG:
                    extra["Strict-Transport-Security"] = (
                        "max-age=63072000; includeSubDomains"
                    )
                for key, value in extra.items():
                    if key.lower().encode() not in present:
                        headers.append((key.lower().encode(), value.encode()))
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Refuse oversized bodies before a handler starts reading them. Uses
    `Content-Length` when sent and counts the stream otherwise, so a
    chunked upload cannot dodge the limit."""

    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in (
            "POST",
            "PUT",
            "PATCH",
        ):
            await self.app(scope, receive, send)
            return
        declared = _content_length(scope)
        if declared is not None and declared > self.limit:
            await _too_large(send, self.limit)
            return

        seen = 0
        tripped = False
        started = False

        async def bounded_receive() -> Message:
            nonlocal seen, tripped
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.limit and not tripped:
                    tripped = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if tripped and not started and message["type"] == "http.response.start":
                started = True
                await _too_large(send, self.limit)
                return
            if tripped:
                return
            started = started or message["type"] == "http.response.start"
            await send(message)

        await self.app(scope, bounded_receive, guarded_send)


def _content_length(scope: Scope) -> int | None:
    for key, value in scope.get("headers", []):
        if key == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _too_large(send: Send, limit: int) -> None:
    response = JSONResponse(
        status_code=413,
        content={
            "errorCode": "REQUEST_TOO_LARGE",
            "message": f"Request body exceeds {limit // (1024 * 1024)} MB.",
            "errors": None,
        },
    )
    await response({"type": "http"}, _noop_receive, send)


async def _noop_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}
