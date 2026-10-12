"""Assemble merged modules around configured backends, including hosted Cloudflare embeddings."""

import importlib
from dataclasses import dataclass, replace

from contextbridge.background.runtime import WorkerProviders
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


def assemble(settings, sessions, backends):
    if not isinstance(backends, IntegrationBackends):
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    for backend, method in [
        (backends.extraction_provider, "generate"),
        (backends.formation_verifier, "verify"),
        (backends.embedding_backend, "embed_batch"),
        (backends.evidence_judge, "judge"),
        (backends.consolidator, "propose"),
        (backends.resolution, "resolve"),
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
    modules = ModuleGateway(
        extractor=(
            Extractor(
                backends.extraction_provider,
                backends.formation_verifier,
                admission_checks=settings.formation_enabled,
            )
            if backends.extraction_provider is not None
            else None
        ),
        admission=(
            AdmissionPolicy(
                backends.formation_verifier,
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
    return WorkerProviders(modules, embedder, EvidenceVerifier(backends.evidence_judge))


def hosted_backends(settings, sessions):
    from contextbridge.engine.resolution import SafeResolutionPolicy
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
    client = QuotaClient(formation, gate=AccountGate(sessions, settings, formation))
    return IntegrationBackends(
        extraction_provider=GroundedProvider(client),
        formation_verifier=BatchVerifier(client),
        duplicate_verifier=BoundedDuplicateVerifier(client),
        resolution=SafeResolutionPolicy(ChatRelationInterpreter(client)),
        evidence_judge=ChatSearchEvidenceJudge(client),
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
