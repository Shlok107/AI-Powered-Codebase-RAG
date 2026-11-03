"""Request body limits for resource-intensive endpoints."""

from starlette.responses import JSONResponse


class RequestBodyTooLarge(Exception):
    """Raised when a streamed request body exceeds the configured limit."""


class UploadBodyLimitMiddleware:
    """Limit upload request bodies before multipart parsing can spool them to disk."""

    def __init__(self, app, *, upload_path: str, max_bytes: int) -> None:
        self.app = app
        self.upload_path = upload_path
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != self.upload_path
        ):
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                await self._reject(scope, receive, send)
                return

        received_bytes = 0
        response_started = False

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_bytes:
                    raise RequestBodyTooLarge
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestBodyTooLarge:
            if not response_started:
                await self._reject(scope, receive, send)

    async def _reject(self, scope, receive, send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": "Upload request exceeds the configured size limit."},
        )
        await response(scope, receive, send)
