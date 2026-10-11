import logging
import secrets
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from contextbridge.config import Settings
from contextbridge.contracts import (
    BrowseQuery,
    BrowseResult,
    CapturedEvent,
    IngestionResponse,
    JobResponse,
)
from contextbridge.db import make_engine, make_session_factory
from contextbridge.engine.browse import BrowseService
from contextbridge.engine.errors import EngineError
from contextbridge.engine.http import CaptureBodyLimit, is_capture_path
from contextbridge.engine.ingestion import IngestionService
from contextbridge.engine.modules import ModuleGateway
from contextbridge.schemas import (
    CreateMemory,
    InspectionResponse,
    MemoryResponse,
    SearchMemories,
    UpdateMemory,
)
from contextbridge.service import MemoryService, MemoryServiceError

bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, *, modules: ModuleGateway | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved = settings or Settings()
        engine = make_engine(resolved)
        app.state.settings = resolved
        app.state.sessions = make_session_factory(engine)
        app.state.modules = modules or ModuleGateway()
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="ContextBridge",
        version="0.1.0",
        lifespan=lifespan,
        description="Explicit memory operations; extraction and semantic search are pending.",
    )
    app.add_middleware(CaptureBodyLimit)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # FastAPI's default response includes raw inputs, which could echo rejected secrets.
        if is_capture_path(request.url.path):
            return JSONResponse(
                status_code=422,
                content={"detail": {"code": "INVALID_INPUT", "retryable": False}},
            )
        return JSONResponse(
            status_code=422,
            content={"detail": [{"loc": e["loc"], "type": e["type"]} for e in exc.errors()]},
        )

    @app.exception_handler(MemoryServiceError)
    async def memory_error(request: Request, exc: MemoryServiceError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("Memory storage operation failed (%s)", type(exc).__name__)
        if is_capture_path(request.url.path):
            return JSONResponse(
                status_code=503,
                content={"detail": {"code": "STORAGE_UNAVAILABLE", "retryable": True}},
            )
        return JSONResponse(status_code=503, content={"detail": "Memory storage unavailable"})

    @app.exception_handler(EngineError)
    async def ingestion_error(request: Request, exc: EngineError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "retryable": exc.retryable}},
        )

    def authenticate(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ):
        expected = request.app.state.settings.api_token.get_secret_value()
        if credentials is None or not secrets.compare_digest(
            credentials.credentials.encode(), expected.encode()
        ):
            raise HTTPException(
                401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
            )

    def session(request: Request) -> Iterator[Session]:
        with request.app.state.sessions() as db:
            yield db

    def service(request: Request, db: Annotated[Session, Depends(session)]) -> MemoryService:
        return MemoryService(db, request.app.state.settings.developer_id)

    Service = Annotated[MemoryService, Depends(service)]
    auth = [Depends(authenticate)]

    def ingestion_service(
        request: Request, db: Annotated[Session, Depends(session)]
    ) -> IngestionService:
        return IngestionService(db, request.app.state.settings)

    Ingestion = Annotated[IngestionService, Depends(ingestion_service)]

    @app.post(
        "/v1/interactions", status_code=202, response_model=IngestionResponse, dependencies=auth
    )
    def ingest(payload: CapturedEvent, engine: Ingestion):
        return engine.ingest(payload)

    @app.get("/v1/jobs/{job_id}", response_model=JobResponse, dependencies=auth)
    def inspect_job(job_id: UUID, engine: Ingestion):
        return engine.inspect_job(job_id)

    @app.post("/v1/inspection/browse", response_model=BrowseResult, dependencies=auth)
    def browse(payload: BrowseQuery, request: Request, db: Annotated[Session, Depends(session)]):
        return BrowseService(db, request.app.state.settings).browse(payload)

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready", dependencies=auth)
    def ready(db: Annotated[Session, Depends(session)]):
        db.execute(text("SELECT claim_key FROM memories LIMIT 1"))
        db.execute(text("SELECT confidence, decision_state FROM memory_versions LIMIT 1"))
        db.execute(text("SELECT 1 FROM capture_events, capture_jobs, capture_candidates LIMIT 1"))
        return {"status": "ready"}

    @app.post("/v1/memories", status_code=201, response_model=MemoryResponse, dependencies=auth)
    def create(payload: CreateMemory, engine: Service):
        return engine.create(payload)

    @app.post("/v1/memories/search", response_model=list[MemoryResponse], dependencies=auth)
    def search(payload: SearchMemories, engine: Service):
        return engine.search(payload)

    @app.get("/v1/memories/{memory_id}", response_model=InspectionResponse, dependencies=auth)
    def inspect(memory_id: UUID, engine: Service):
        return engine.inspect(memory_id)

    @app.put("/v1/memories/{memory_id}", response_model=MemoryResponse, dependencies=auth)
    def update(memory_id: UUID, payload: UpdateMemory, engine: Service):
        return engine.update(memory_id, payload)

    @app.delete("/v1/memories/{memory_id}", status_code=204, dependencies=auth)
    def forget(memory_id: UUID, engine: Service):
        engine.forget(memory_id)
        return Response(status_code=204)

    return app
