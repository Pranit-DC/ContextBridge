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

from contextbridge.background.runner import WorkRunner
from contextbridge.config import Settings
from contextbridge.context_models import ContextQuery, ContextResult
from contextbridge.contracts import (
    BrowseQuery,
    BrowseResult,
    CapturedEvent,
    IngestionResponse,
    JobResponse,
    MemoryRecord,
    RetrievalQuery,
    RetrievalResult,
)
from contextbridge.db import make_engine, make_session_factory
from contextbridge.engine.browse import BrowseService
from contextbridge.engine.context import MemoryContextService
from contextbridge.engine.errors import EngineError
from contextbridge.engine.http import CaptureBodyLimit, is_capture_path
from contextbridge.engine.ingestion import IngestionService
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.retrieval import RetrievalService
from contextbridge.evidence_time.contracts import (
    EvidenceBundle,
    ProvenanceQuery,
    ProvenanceResult,
    TemporalContextQuery,
)
from contextbridge.management import (
    CompactionResult,
    CompactMemories,
    ConsolidationRequest,
    ConsolidationSubmission,
    IndexingState,
    LifecycleResult,
    LifecycleState,
    RestoreMemory,
    RetiredQuery,
    RetiredResult,
    RetireMemory,
    RuntimeState,
)
from contextbridge.query_models import ReferencedQuery
from contextbridge.schemas import (
    CreateMemory,
    Identifier,
    InspectionResponse,
    MemoryResponse,
    SearchMemories,
    UpdateMemory,
)
from contextbridge.service import MemoryService, MemoryServiceError

bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    modules: ModuleGateway | None = None,
    embedder=None,
    verifier=None,
    context_verifier=None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved = settings or Settings()
        engine = make_engine(resolved)
        app.state.settings = resolved
        app.state.sessions = make_session_factory(engine)
        try:
            providers = None
            if modules is None and (
                resolved.integration_factory is not None
                or resolved.embedding_provider is not None
                or resolved.formation_enabled
            ):
                from contextbridge.runtime import load_integration

                providers = load_integration(resolved, app.state.sessions)
            app.state.modules = (
                modules
                if modules is not None
                else (providers.modules if providers else ModuleGateway())
            )
            app.state.embedder = (
                embedder if embedder is not None else (providers.embedder if providers else None)
            )
            app.state.verifier = (
                verifier if verifier is not None else (providers.verifier if providers else None)
            )
            app.state.providers = providers
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="ContextBridge",
        version="0.1.0",
        lifespan=lifespan,
        description="Evidence-backed memory with optional configured extraction and retrieval.",
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
            # Rejected extra field names and dictionary keys can also contain secrets.
            content={"detail": [{"loc": [e["loc"][0]], "type": e["type"]} for e in exc.errors()]},
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

    @app.post(
        "/v2/interactions/bundles",
        status_code=202,
        response_model=IngestionResponse,
        dependencies=auth,
    )
    def ingest_evidence_bundle(
        payload: EvidenceBundle, request: Request, db: Annotated[Session, Depends(session)]
    ):
        from contextbridge.evidence_time.ingestion import ingest_bundle

        return ingest_bundle(db, request.app.state.settings, payload)

    @app.get("/v2/status", dependencies=auth)
    def evidence_time_status(request: Request):
        return {
            "schema_version": 2,
            "bundle_import_enabled": request.app.state.settings.capture_evidence_v2_enabled,
        }

    @app.post("/v2/inspection/provenance", response_model=ProvenanceResult, dependencies=auth)
    def inspect_provenance(
        payload: ProvenanceQuery, request: Request, db: Annotated[Session, Depends(session)]
    ):
        from contextbridge.evidence_time.inspection import provenance

        return provenance(db, request.app.state.settings, payload)

    @app.post("/v2/retrieval/temporal-context", dependencies=auth)
    def inspect_temporal_context(
        payload: TemporalContextQuery, request: Request, db: Annotated[Session, Depends(session)]
    ):
        from contextbridge.evidence_time.inspection import temporal_context

        return temporal_context(db, request.app.state.settings, payload)

    @app.get("/v1/jobs", response_model=list[JobResponse], dependencies=auth)
    def recent_jobs(project_id: Identifier, engine: Ingestion):
        return engine.recent_jobs(project_id)

    @app.get("/v1/worker/jobs/{work_id}", dependencies=auth)
    def inspect_work(work_id: UUID, request: Request):
        return WorkRunner(request.app.state.sessions, request.app.state.settings, None).inspect(
            work_id
        )

    @app.post("/v1/inspection/browse", response_model=BrowseResult, dependencies=auth)
    def browse(payload: BrowseQuery, request: Request, db: Annotated[Session, Depends(session)]):
        return BrowseService(db, request.app.state.settings).browse(payload)

    @app.post("/v1/retrieval/search", response_model=RetrievalResult, dependencies=auth)
    def retrieve(
        payload: RetrievalQuery, request: Request, db: Annotated[Session, Depends(session)]
    ):
        providers = request.app.state.providers
        providers = providers.fresh() if providers is not None else None
        return RetrievalService(
            db,
            request.app.state.settings,
            providers.modules if providers else request.app.state.modules,
            embedder
            if embedder is not None
            else (providers.embedder if providers else request.app.state.embedder),
            verifier
            if verifier is not None
            else (providers.verifier if providers else request.app.state.verifier),
        ).search(payload)

    @app.post("/v1/retrieval/referenced-search", response_model=RetrievalResult, dependencies=auth)
    def followup(
        payload: ReferencedQuery, request: Request, db: Annotated[Session, Depends(session)]
    ):
        from contextbridge.engine.query_references import referenced_search

        providers = request.app.state.providers
        providers = providers.fresh() if providers is not None else None
        return referenced_search(
            db,
            request.app.state.settings,
            providers.modules if providers else request.app.state.modules,
            payload,
            embedder=embedder
            if embedder is not None
            else (providers.embedder if providers else request.app.state.embedder),
            verifier=verifier
            if verifier is not None
            else (providers.verifier if providers else request.app.state.verifier),
        )

    @app.post("/v1/retrieval/context", response_model=ContextResult, dependencies=auth)
    def memory_context(
        payload: ContextQuery, request: Request, db: Annotated[Session, Depends(session)]
    ):
        providers = request.app.state.providers
        providers = providers.fresh() if providers is not None else None
        active_verifier = context_verifier if context_verifier is not None else verifier
        if active_verifier is None:
            active_verifier = (
                (
                    providers.context_verifier
                    if providers.context_verifier is not None
                    else providers.verifier
                )
                if providers
                else request.app.state.verifier
            )
        return MemoryContextService(db, request.app.state.settings, active_verifier).inspect(
            payload
        )

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/v1/status", response_model=RuntimeState, dependencies=auth)
    def capabilities(request: Request):
        configuration = request.app.state.settings
        modules = request.app.state.modules
        return {
            "capture_project_id": configuration.capture_project_id,
            "developer_capture_enabled": configuration.capture_allow_developer,
            "extraction_configured": modules.extractor is not None,
            "consolidation_configured": modules.consolidator is not None,
            "embeddings_configured": request.app.state.embedder is not None,
            "default_context_limit": 3,
            "viewer_context_limit": 5,
            "provider_connection": "not_probed",
        }

    @app.get("/health/ready", dependencies=auth)
    def ready(db: Annotated[Session, Depends(session)]):
        db.execute(text("SELECT claim_key, retired_at FROM memories LIMIT 1"))
        db.execute(text("SELECT 1 FROM provider_quotas LIMIT 1"))
        db.execute(text("SELECT confidence, decision_state FROM memory_versions LIMIT 1"))
        db.execute(text("SELECT 1 FROM capture_events, capture_jobs, capture_candidates LIMIT 1"))
        db.execute(
            text(
                "SELECT 1 FROM memory_embeddings, embedding_models, "
                "reindex_jobs, reindex_targets LIMIT 1"
            )
        )
        db.execute(
            text("SELECT 1 FROM work_items, consolidation_jobs, consolidation_sources LIMIT 1")
        )
        db.execute(
            text("SELECT 1 FROM capture_bundles, candidate_provenance, version_provenance LIMIT 1")
        )
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

    @app.get("/v1/memories/{memory_id}/lifecycle", response_model=LifecycleState, dependencies=auth)
    def lifecycle(memory_id: UUID, engine: Service):
        memory = engine.get_memory(memory_id)
        return {"retired_at": memory.retired_at, "current_version": memory.current_version}

    @app.get(
        "/v1/memories/{memory_id}/sources", response_model=list[MemoryRecord], dependencies=auth
    )
    def derivation_sources(memory_id: UUID, engine: Service):
        from sqlalchemy import select

        from contextbridge.models import Memory, MemoryEdge, MemoryVersion
        from contextbridge.persistence.records import record_response

        memory = engine.get_memory(memory_id)
        current_id = engine.session.scalar(
            select(MemoryVersion.id).where(
                MemoryVersion.memory_id == memory_id, MemoryVersion.number == memory.current_version
            )
        )
        rows = engine.session.execute(
            select(Memory, MemoryVersion)
            .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
            .join(MemoryEdge, MemoryEdge.to_version_id == MemoryVersion.id)
            .where(
                MemoryEdge.from_version_id == current_id,
                MemoryEdge.relation == "derived_from",
                Memory.developer_id == engine.developer_id,
                Memory.scope == memory.scope,
                Memory.project_id.is_not_distinct_from(memory.project_id),
            )
            .order_by(MemoryVersion.id)
            .limit(200)
        ).all()
        return [record_response(m, v) for m, v in rows]

    @app.get("/v1/memories/{memory_id}/indexing", response_model=IndexingState, dependencies=auth)
    def indexing_status(memory_id: UUID, request: Request, engine: Service):
        from sqlalchemy import select

        from contextbridge.models import MemoryEmbedding, MemoryVersion, ReindexJob, ReindexTarget

        memory = engine.get_memory(memory_id)
        configuration = request.app.state.settings
        state = "awaiting_worker" if configuration.embedding_model_id else "not_configured"
        if memory.retired_at is not None:
            state = "retired"
        elif configuration.embedding_model_id:
            version = engine.session.scalar(
                select(MemoryVersion.id).where(
                    MemoryVersion.memory_id == memory_id,
                    MemoryVersion.number == memory.current_version,
                )
            )
            embedded = engine.session.scalar(
                select(MemoryEmbedding.version_id).where(
                    MemoryEmbedding.version_id == version,
                    MemoryEmbedding.developer_id == configuration.developer_id,
                    MemoryEmbedding.model_id == configuration.embedding_model_id,
                    MemoryEmbedding.dimensions == configuration.embedding_dimensions,
                )
            )
            if embedded is not None:
                state = "succeeded"
            else:
                latest = engine.session.scalar(
                    select(ReindexJob.status)
                    .join(ReindexTarget)
                    .where(
                        ReindexTarget.version_id == version,
                        ReindexJob.developer_id == configuration.developer_id,
                        ReindexJob.model_id == configuration.embedding_model_id,
                        ReindexJob.dimensions == configuration.embedding_dimensions,
                        ReindexJob.scope == memory.scope,
                        ReindexJob.project_id.is_not_distinct_from(memory.project_id),
                    )
                    .order_by(ReindexJob.updated_at.desc())
                    .limit(1)
                )
                bound = (
                    memory.scope == "project"
                    and memory.project_id == configuration.capture_project_id
                    or memory.scope == "developer"
                    and configuration.capture_allow_developer
                )
                state = latest or (state if bound else "not_configured")
        return IndexingState(current_version=memory.current_version, status=state)

    @app.post("/v1/memories/{memory_id}/retire", response_model=LifecycleResult, dependencies=auth)
    def retire(memory_id: UUID, payload: RetireMemory, engine: Service):
        return engine.retire(memory_id, payload)

    @app.post("/v1/memories/{memory_id}/restore", response_model=LifecycleResult, dependencies=auth)
    def restore(memory_id: UUID, payload: RestoreMemory, engine: Service):
        return engine.restore(memory_id, payload)

    @app.post("/v1/inspection/retired", response_model=RetiredResult, dependencies=auth)
    def retired(payload: RetiredQuery, engine: Service):
        return engine.retired(payload)

    @app.post("/v1/maintenance/compact", response_model=CompactionResult, dependencies=auth)
    def compact(payload: CompactMemories, engine: Service):
        from contextbridge.engine.compaction import compact

        return compact(engine, payload)

    @app.post("/v1/consolidations", response_model=ConsolidationSubmission, dependencies=auth)
    def consolidate(
        payload: ConsolidationRequest, request: Request, db: Annotated[Session, Depends(session)]
    ):
        from contextbridge.engine.consolidation_queue import submit

        if request.app.state.modules.consolidator is None:
            raise EngineError("PROVIDER_UNAVAILABLE", 503)
        return submit(db, request.app.state.settings, payload)

    @app.get("/v1/consolidations/{job_id}", dependencies=auth)
    def consolidation_status(
        job_id: UUID, request: Request, db: Annotated[Session, Depends(session)]
    ):
        from contextbridge.engine.consolidation import ConsolidationService
        from contextbridge.engine.consolidation_queue import scoped_job

        scoped_job(db, request.app.state.settings, job_id)
        return ConsolidationService(db, request.app.state.settings).inspect(job_id)

    @app.put("/v1/memories/{memory_id}", response_model=MemoryResponse, dependencies=auth)
    def update(memory_id: UUID, payload: UpdateMemory, engine: Service):
        return engine.update(memory_id, payload)

    @app.delete("/v1/memories/{memory_id}", status_code=204, dependencies=auth)
    def forget(memory_id: UUID, engine: Service):
        engine.forget(memory_id)
        return Response(status_code=204)

    return app
