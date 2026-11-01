"""Loopback control plane with one-time browser bootstrap; never a second memory engine."""

import json
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from contextbridge.local_ui.actions import check_provider
from contextbridge.local_ui.settings import KeyChange, Preferences, SettingsError
from contextbridge.product.integrations import integration
from contextbridge.product.services import Services
from contextbridge.product.settings import ProductSettings
from contextbridge.schemas import Identifier, StrictModel

MAX_BODY = 524_288
COOKIE = "contextbridge_session"
# All paths are relative to a fixed loopback API origin; arbitrary URLs/headers are refused.
ALLOWED = re.compile(
    r"^(?:health/(?:ready|live)|v1/(?:status|memories(?:/[0-9a-f-]{36}(?:/(?:sources|indexing|lifecycle|retire|restore))?|/search)?|"
    r"inspection/(?:browse|retired)|retrieval/(?:search|context|referenced-search)|"
    r"maintenance/(?:compact|compact-semantic)|consolidations(?:/[0-9a-f-]{36})?|"
    r"interactions|jobs(?:/[0-9a-f-]{36})?)|v2/(?:status|interactions/bundles|"
    r"inspection/provenance|retrieval/temporal-context))$"
)


class SaveSettings(StrictModel):
    revision: str
    preferences: Preferences
    groq: KeyChange = Field(default_factory=KeyChange)
    cloudflare: KeyChange = Field(default_factory=KeyChange)


class Revision(StrictModel):
    revision: str
    confirmed: bool = Field(default=False, strict=True)


class Migrate(Revision):
    file_revision: str


class ProviderCheck(Revision):
    provider: Literal["groq", "cloudflare"]


class Connection(StrictModel):
    workspace: str = Field(min_length=1, max_length=4096)
    project: Identifier
    action: Literal["status", "preview", "install", "pause", "remove"] = "status"
    confirmed: bool = Field(default=False, strict=True)


def create_product_app(
    root, *, port=8501, settings=None, services=None, transport=None, operator_key=None
):
    root = Path(root).resolve()
    settings = settings or ProductSettings(root / ".env")
    services = services or Services(settings, root)
    origin = f"http://127.0.0.1:{port}"
    operator_key = operator_key or secrets.token_urlsafe(32)
    handshake, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    cookie = secrets.token_urlsafe(32)
    state = {
        "launch": handshake,
        "deadline": time.monotonic() + 120,
        "used": False,
        "authenticated": False,
        "session_deadline": 0,
    }
    handshake_lock = threading.Lock()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.launch_url = f"{origin}/#launch={handshake}"
    app.state.settings, app.state.services = settings, services

    def issue_launch():
        with handshake_lock:
            state.update(
                launch=secrets.token_urlsafe(32), used=False, deadline=time.monotonic() + 120
            )
            app.state.launch_url = f"{origin}/#launch={state['launch']}"
            return app.state.launch_url

    app.state.issue_launch = issue_launch

    web = Path(__file__).parent / "web"
    hashes_path = web / "csp.json"
    script_hashes = " ".join(json.loads(hashes_path.read_text())) if hashes_path.is_file() else ""

    @app.middleware("http")
    async def boundary(request, call_next):
        if request.headers.get("host") != f"127.0.0.1:{port}":
            return JSONResponse({"detail": "Use the local launcher address."}, 403)
        if request.url.path.startswith("/api/"):
            operator = request.url.path == "/api/local/v1/operator"
            if operator and not secrets.compare_digest(
                request.headers.get("x-local-operator", ""), operator_key
            ):
                return JSONResponse({"detail": "Local operator access required."}, 401)
            if request.headers.get("origin") not in (None, origin):
                return JSONResponse({"detail": "Local origin required."}, 403)
            if (
                request.method not in ("GET", "HEAD")
                and request.headers.get("origin") != origin
                and not operator
            ):
                return JSONResponse({"detail": "Local origin required."}, 403)
            if not operator and not (
                request.url.path == "/api/local/v1/session" and request.method == "POST"
            ):
                if (
                    not state["authenticated"]
                    or time.monotonic() > state["session_deadline"]
                    or not secrets.compare_digest(request.cookies.get(COOKIE, ""), cookie)
                ):
                    return JSONResponse({"detail": "Open the workspace through its launcher."}, 401)
                if request.method != "GET" and not secrets.compare_digest(
                    request.headers.get("x-csrf-token", ""), csrf
                ):
                    return JSONResponse({"detail": "Refresh this local session."}, 403)
            raw = bytearray()
            async for chunk in request.stream():
                if len(raw) + len(chunk) > MAX_BODY:
                    return JSONResponse({"detail": "Request too large."}, 413)
                raw.extend(chunk)
            request._body = bytes(raw)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": f"default-src 'self'; "
                f"script-src 'self' {script_hashes}; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
                "frame-ancestors 'none'; object-src 'none'; base-uri 'self'",
            }
        )
        return response

    @app.exception_handler(SettingsError)
    async def settings_error(request, error):
        return JSONResponse({"detail": str(error)}, 409)

    @app.exception_handler(OSError)
    async def file_error(request, error):
        return JSONResponse(
            {"detail": "Local files could not be updated. Check permissions, reload and retry."},
            409,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request, error):
        return JSONResponse({"detail": "Check the form fields; nothing was accepted."}, 422)

    @app.post("/api/local/v1/session")
    async def session(request: Request):
        try:
            value = await request.json()
            with handshake_lock:
                if (
                    not isinstance(value, dict)
                    or state["used"]
                    or time.monotonic() > state["deadline"]
                    or not secrets.compare_digest(value.get("launch", ""), state["launch"])
                ):
                    raise ValueError
                state["used"], state["authenticated"] = True, True
                state["session_deadline"] = time.monotonic() + 43_200
        except (ValueError, TypeError):
            raise HTTPException(
                401, "Launch link expired. Reopen using contextbridge start."
            ) from None
        result = JSONResponse({"csrf": csrf})
        result.set_cookie(COOKIE, cookie, httponly=True, samesite="strict", max_age=43_200)
        return result

    @app.get("/api/local/v1/session")
    def session_status():
        # This route also needs the cookie; only the POST exchanges a launch token.
        return {"csrf": csrf}

    @app.post("/api/local/v1/operator", include_in_schema=False)
    async def operator(request: Request):
        try:
            body = await request.json()
            action = body.get("action") if isinstance(body, dict) else None
        except ValueError:
            action = None
        if action == "open":
            return {"url": issue_launch()}
        if action == "status":
            return services.status()
        if action == "stop":
            from starlette.concurrency import run_in_threadpool

            await run_in_threadpool(services.stop)
            callback = getattr(app.state, "shutdown", None)
            if callback:
                threading.Timer(0.2, callback).start()
            return {"stopped": True}
        raise HTTPException(422, "Choose a supported operator action.")

    @app.get("/api/local/v1/config")
    def config():
        return settings.public()

    @app.put("/api/local/v1/config")
    def save(payload: SaveSettings):
        if not services.lock.acquire(blocking=False):
            raise SettingsError("Another service operation is running.")
        try:
            if payload.groq.action != "keep" or payload.cloudflare.action != "keep":
                current = settings.record()
                if current.groq or current.cloudflare or services.status()["docker_available"]:
                    services.pause()
            return settings.save(
                payload.revision, payload.preferences, payload.groq, payload.cloudflare
            )
        finally:
            services.lock.release()

    @app.post("/api/local/v1/migrate")
    def migrate(payload: Migrate):
        if not payload.confirmed:
            raise SettingsError("Confirm migration and pausing provider services first.")
        if not services.lock.acquire(blocking=False):
            raise SettingsError("Another service operation is running.")
        try:
            settings.record()
            services.pause()
            return settings.migrate(payload.revision, payload.file_revision)
        finally:
            services.lock.release()

    @app.post("/api/local/v1/providers/check")
    def check(payload: ProviderCheck):
        if not services.lock.acquire(blocking=False):
            raise SettingsError("Another service operation is running.")
        try:
            record = settings.record()
            if record.revision != payload.revision:
                raise SettingsError("Settings changed. Reload before checking.")
            memory = settings.runtime(record)
            ok, message = check_provider(
                memory,
                payload.provider,
                memory.snapshot().revision,
                consent=payload.confirmed,
                transport=transport,
            )
            return {"ok": ok, "message": message}
        finally:
            services.lock.release()

    @app.get("/api/local/v1/services")
    def status():
        return services.status()

    @app.post("/api/local/v1/services/{action}")
    def service_action(action: str, payload: Revision):
        if not payload.confirmed or action not in ("apply", "stop", "offline"):
            raise SettingsError("Confirm the selected service operation first.")
        if action in ("apply", "offline"):
            services.apply(payload.revision, offline=action == "offline")
        else:
            services.stop()
        return services.status()

    @app.post("/api/local/v1/connections/codex")
    def codex(payload: Connection):
        if payload.action in ("install", "pause", "remove") and not payload.confirmed:
            raise SettingsError("Confirm the workspace capture change first.")
        return integration(payload.workspace, payload.project, root / ".env.mcp", payload.action)

    @app.get("/api/local/v1/connections/mcp")
    def mcp(project: Identifier = "contextbridge"):
        import sys

        return {
            "command": sys.executable,
            "args": [
                "-m",
                "contextbridge.mcp_adapter.cli",
                "--env-file",
                str(root / ".env.mcp"),
                "--project-id",
                project,
            ],
            "notice": "Use the same project ID in each agent. "
            "Configuration references a private file; no provider keys are included.",
        }

    @app.api_route(
        "/api/memory/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False
    )
    async def proxy(path: str, request: Request):
        if not ALLOWED.fullmatch(path):
            raise HTTPException(404, "Unsupported memory operation.")
        values = settings.legacy.read()[2]
        token = values.get("CONTEXTBRIDGE_API_TOKEN")
        if not token:
            raise HTTPException(503, "Local service access is not configured.")
        try:
            # No caller headers, destination, redirects, proxies or unbounded responses.
            async with httpx.AsyncClient(
                transport=transport, trust_env=False, follow_redirects=False, timeout=90
            ) as client:
                async with client.stream(
                    request.method,
                    "http://127.0.0.1:8000/" + path,
                    params=request.query_params,
                    content=await request.body(),
                    headers={
                        "Authorization": "Bearer " + token,
                        "Content-Type": "application/json",
                    },
                ) as response:
                    raw = bytearray()
                    async for part in response.aiter_bytes():
                        if len(raw) + len(part) > 8_388_608:
                            raise ValueError
                        raw.extend(part)
                    if response.status_code >= 500:
                        raise ValueError
                    if response.status_code == 204:
                        from fastapi import Response

                        return Response(status_code=204)
                    return JSONResponse(json.loads(raw), response.status_code)
        except (httpx.HTTPError, ValueError):
            raise HTTPException(
                503, "Memory service unavailable. Start services or review Activity."
            ) from None

    web = Path(__file__).parent / "web"
    if web.is_dir():
        app.mount("/", StaticFiles(directory=web, html=True), name="workspace")
    else:

        @app.get("/")
        def missing_assets():
            return JSONResponse(
                {"detail": "Build the frontend or install a release with bundled UI assets."}, 503
            )

    return app
