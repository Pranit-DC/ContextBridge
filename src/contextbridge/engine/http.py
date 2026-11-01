"""Bound ingestion bodies before parsing; leave existing API request behavior intact."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Includes JSON-escaped non-BMP Unicode in a maximum-size, otherwise valid event.
MAX_CAPTURE_BODY_BYTES = 512 * 1024


def is_capture_path(path: str) -> bool:
    return path.rstrip("/") in {
        "/v1/interactions",
        "/v2/interactions/bundles",
        "/v2/inspection/provenance",
        "/v2/retrieval/temporal-context",
        "/v1/inspection/browse",
        "/v1/retrieval/search",
    } or path.startswith(("/v1/jobs/", "/v1/worker/jobs/"))


class CaptureBodyLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or not is_capture_path(scope["path"]):
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_CAPTURE_BODY_BYTES:
                response = JSONResponse(
                    status_code=422,
                    content={"detail": {"code": "INVALID_INPUT", "retryable": False}},
                )
                await response(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, bounded_receive, send)
