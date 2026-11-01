"""Assemble merged modules around configured backends, including hosted Cloudflare embeddings."""

import importlib
from dataclasses import dataclass, replace

from contextbridge.background.runtime import WorkerProviders
from contextbridge.engine.context_judge import ContextEvidenceJudge
from contextbridge.engine.errors import ModuleError
from contextbridge.engine.event_reader import EventReader
from contextbridge.engine.modules import ModuleGateway
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.retrieval.cloudflare import CloudflareEmbeddingBackend
from contextbridge.retrieval.embedding import GuardedEmbeddingProvider
from contextbridge.retrieval.retriever import RetrievalConfig, Retriever
from contextbridge.retrieval.verifier import EvidenceVerifier


@dataclass(frozen=True)
class IntegrationBackends:
    """The factory supplies providers, never a separate memory store or canned production data.

    The factory owns its supplied providers' URL/model/credential settings. Configured Cloudflare
    embeddings fill only a missing backend in ``load_integration``.
    Construct clients here; generating/embedding private input is a later explicit operation.
    """

    extraction_provider: object | None = None
    formation_verifier: object | None = None
    embedding_backend: object | None = None
    evidence_judge: object | None = None
    consolidator: object | None = None
    resolution: object | None = None
    duplicate_verifier: object | None = None
    execution_guard: object | None = None
    context_evidence_judge: object | None = None
    compaction_verifier: object | None = None


class HostedRelationBoundary:
    """Defer ambiguous category drift unsupported by the built-in hosted adapter.

    The adapter currently returns unrelated without comparing different types. That is not
    evidence of compatibility. Preserve the shared policy's ability to use injected interpreters
    that do support these comparisons; only this built-in adapter needs conservative deferral.
    """

    def __init__(self, interpreter):
        self.interpreter = interpreter
        self.client = interpreter.client

    def compare(self, candidate, record):
        if candidate["type"] != record["memory"]["type"] and (
            candidate["claim_key"] is None
            or record["claim_key"] is None
            or candidate["claim_key"] == record["claim_key"]
        ):
            return "uncertain"
        return self.interpreter.compare(candidate, record)


def assemble(settings, sessions, backends):
    if not isinstance(backends, IntegrationBackends):
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    if backends.execution_guard is not None and not callable(backends.execution_guard):
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    for backend, method in [
        (backends.extraction_provider, "generate"),
        (backends.formation_verifier, "verify"),
        (backends.embedding_backend, "embed_batch"),
        (backends.evidence_judge, "judge"),
        (backends.context_evidence_judge, "judge"),
        (backends.consolidator, "propose"),
        (backends.resolution, "resolve"),
        (backends.compaction_verifier, "verify"),
        (backends.compaction_verifier, "bind_guard"),
        (backends.duplicate_verifier, "compare"),
    ]:
        if backend is not None and not callable(getattr(backend, method, None)):
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
    if (backends.extraction_provider is None) != (backends.formation_verifier is None):
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    if (backends.embedding_backend is None) != (settings.embedding_model_id is None):
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    embedder = None
    if backends.embedding_backend is not None:
        embedder = GuardedEmbeddingProvider(
            backends.embedding_backend,
            model_id=settings.embedding_model_id,
            dimensions=settings.embedding_dimensions,
            max_texts=200,
            timeout_seconds=settings.provider_timeout_seconds,
        )
    formation_verifier = backends.formation_verifier
    extractor = (
        Extractor(
            backends.extraction_provider,
            backends.formation_verifier,
            admission_checks=settings.formation_enabled,
        )
        if backends.extraction_provider is not None
        else None
    )
    if settings.capture_evidence_v2_enabled and extractor is not None:
        from contextbridge.evidence_time.runtime import BundleAwareExtractor, BundleAwareVerifier

        client = getattr(backends.extraction_provider, "client", None)
        extractor = BundleAwareExtractor(extractor, client, sessions, settings)
        formation_verifier = BundleAwareVerifier(formation_verifier, client, sessions, settings)
    modules = ModuleGateway(
        extractor=extractor,
        admission=(
            AdmissionPolicy(
                formation_verifier,
                EventReader(sessions, settings),
                duplicate_verifier=backends.duplicate_verifier,
            )
            if backends.formation_verifier is not None
            else None
        ),
        resolution=backends.resolution,
        retriever=Retriever(
            RetrievalConfig(
                embedding_model_id=settings.embedding_model_id,
                embedding_dimensions=settings.embedding_dimensions,
                expand_graph=settings.retrieval_expand_graph or settings.formation_enabled,
                verify_types=frozenset({"DECISION"})
                if settings.retrieval_check_decisions or settings.formation_enabled
                else frozenset(),
            )
        ),
        consolidator=backends.consolidator,
    )
    return WorkerProviders(
        modules,
        embedder,
        EvidenceVerifier(backends.evidence_judge),
        context_verifier=EvidenceVerifier(
            backends.context_evidence_judge
            if backends.context_evidence_judge is not None
            else backends.evidence_judge
        ),
        execution_guard=backends.execution_guard,
        compaction_verifier=backends.compaction_verifier,
    )


def hosted_backends(settings, sessions):
    from contextbridge.engine.resolution import SafeResolutionPolicy
    from contextbridge.engine.semantic_compaction import ChatCompactionVerifier
    from contextbridge.formation.consolidation import Consolidator
    from contextbridge.formation.providers.bounded import QuotaClient
    from contextbridge.formation.providers.config import load_settings
    from contextbridge.formation.providers.grounded import (
        BatchVerifier,
        BoundedDuplicateVerifier,
        GroundedProvider,
    )
    from contextbridge.formation.providers.interpretation import (
        ChatRelationInterpreter,
        ChatSearchEvidenceJudge,
    )
    from contextbridge.formation.providers.semantic import (
        ChatConsolidationVerifier,
        ChatGroupingProvider,
    )
    from contextbridge.persistence.provider_quota import AccountGate

    formation = load_settings()
    formation.check_execution()
    if not formation.is_groq_free() or formation.verifier_model not in (None, formation.model):
        raise ModuleError("INVALID_INPUT")
    # Bound the runtime output independently of larger offline evaluation experiments.
    formation = formation.model_copy(
        update={"max_output_tokens": min(formation.max_output_tokens, 1024)}
    )
    client = QuotaClient(
        formation, gate=AccountGate(sessions, settings, formation, max_wait_seconds=61)
    )
    search_client = QuotaClient(formation, gate=AccountGate(sessions, settings, formation))
    context_client = QuotaClient(
        formation, gate=AccountGate(sessions, settings, formation, max_wait_seconds=7)
    )
    return IntegrationBackends(
        compaction_verifier=ChatCompactionVerifier(
            QuotaClient(
                formation,
                max_calls=1,
                gate=AccountGate(sessions, settings, formation, max_wait_seconds=7),
            )
        ),
        extraction_provider=GroundedProvider(client),
        formation_verifier=BatchVerifier(client),
        duplicate_verifier=BoundedDuplicateVerifier(client),
        resolution=SafeResolutionPolicy(HostedRelationBoundary(ChatRelationInterpreter(client))),
        evidence_judge=ChatSearchEvidenceJudge(search_client),
        context_evidence_judge=ContextEvidenceJudge(context_client),
        execution_guard=lambda guard: setattr(client, "before_call", guard),
        consolidator=Consolidator(ChatGroupingProvider(client), ChatConsolidationVerifier(client)),
    )


def load_integration(settings, sessions, *, _fresh=False):
    if (
        settings.integration_factory is None
        and settings.embedding_provider is None
        and not settings.formation_enabled
    ):
        raise ModuleError("PROVIDER_UNAVAILABLE")
    try:
        backends = IntegrationBackends()
        if settings.integration_factory is not None:
            module, name = settings.integration_factory.split(":")
            factory = getattr(importlib.import_module(module), name)
            backends = factory(settings, sessions)
        if not isinstance(backends, IntegrationBackends):
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        if (backends.extraction_provider is None) != (backends.formation_verifier is None):
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        if settings.formation_enabled:
            hosted = hosted_backends(settings, sessions)
            if backends.context_evidence_judge is None and backends.evidence_judge is None:
                backends = replace(backends, context_evidence_judge=hosted.context_evidence_judge)
            # A custom factory retains each provider it supplies. Fill missing providers only.
            backends = replace(
                backends,
                **{
                    name: getattr(hosted, name)
                    for name in (
                        "extraction_provider",
                        "formation_verifier",
                        "duplicate_verifier",
                        "resolution",
                        "evidence_judge",
                        "consolidator",
                        "execution_guard",
                        "compaction_verifier",
                    )
                    if getattr(backends, name) is None
                },
            )
        if backends.embedding_backend is None and settings.embedding_provider == "cloudflare":
            backends = replace(
                backends,
                embedding_backend=CloudflareEmbeddingBackend(
                    api_key=settings.embedding_api_key.get_secret_value(),
                    base_url=settings.embedding_base_url.get_secret_value(),
                    model_id=settings.embedding_model_id,
                    dimensions=settings.embedding_dimensions,
                    timeout_seconds=settings.provider_timeout_seconds,
                ),
            )
        providers = assemble(settings, sessions, backends)
        return (
            providers
            if _fresh
            else replace(
                providers, factory=lambda: load_integration(settings, sessions, _fresh=True)
            )
        )
    except ModuleError as error:
        raise ModuleError(error.code, retryable=error.retryable) from None
    except Exception:
        raise ModuleError("INVALID_PROVIDER_OUTPUT") from None
