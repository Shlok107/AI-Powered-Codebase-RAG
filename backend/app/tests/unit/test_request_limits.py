import pytest

from app.core.request_limits import UploadBodyLimitMiddleware


pytestmark = pytest.mark.unit


def _scope(headers=(), path="/api/v1/repositories/upload", method="POST"):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": list(headers),
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
    }


async def _run(middleware, scope, chunks):
    messages = []
    chunks = iter(chunks)

    async def receive():
        try:
            return {"type": "http.request", "body": next(chunks), "more_body": True}
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await middleware(scope, receive, send)
    return messages


@pytest.mark.asyncio
async def test_upload_limit_rejects_oversized_content_length_before_body_parsing() -> None:
    async def app(_scope, _receive, _send):
        pytest.fail("The app must not parse an upload whose declared body is oversized")

    middleware = UploadBodyLimitMiddleware(app, upload_path="/upload", max_bytes=10)
    messages = await _run(middleware, _scope([(b"content-length", b"11")], "/upload"), [b"x" * 11])

    assert messages[0]["status"] == 413
    assert b"configured size limit" in messages[1]["body"]


@pytest.mark.asyncio
async def test_upload_limit_counts_chunked_body_bytes() -> None:
    async def app(_scope, receive, _send):
        while (await receive())["more_body"]:
            pass

    middleware = UploadBodyLimitMiddleware(app, upload_path="/upload", max_bytes=3)
    messages = await _run(middleware, _scope(path="/upload"), [b"ab", b"cd"])

    assert messages[0]["status"] == 413


@pytest.mark.asyncio
async def test_upload_limit_does_not_restrict_other_api_requests() -> None:
    reached_app = False

    async def app(_scope, _receive, _send):
        nonlocal reached_app
        reached_app = True

    middleware = UploadBodyLimitMiddleware(app, upload_path="/upload", max_bytes=1)
    await _run(middleware, _scope(path="/api/v1/chat"), [b"oversized for upload"])

    assert reached_app
