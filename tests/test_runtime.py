import traceback
from dataclasses import replace

import pytest
from pydantic import ValidationError

from contextbridge.config import Settings
from contextbridge.engine.errors import ModuleError
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.runtime import IntegrationBackends, assemble, load_integration
from tests.conftest import TEST_TOKEN
from tests.integration.provider_factory import make


def settings(**changes):
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused/unused_test",
        api_token=TEST_TOKEN,
        integration_factory="tests.integration.provider_factory:make",
        embedding_model_id="recorded-integration-v1",
        embedding_dimensions=2,
        **changes,
    )


def test_real_modules_share_embedding_metadata_without_calling_backends():
    configuration = settings()
    providers = assemble(configuration, None, make(configuration, None))
    assert isinstance(providers.modules.extractor, Extractor)
    assert isinstance(providers.modules.admission, AdmissionPolicy)
    assert providers.modules.retriever.config.embedding_model_id == providers.embedder.model_id
    assert providers.modules.retriever.config.embedding_dimensions == providers.embedder.dimensions
    assert providers.embedder.max_texts == 200
    assert not providers.modules.retriever.config.expand_graph
    assert providers.modules.retriever.config.verify_types == frozenset()


@pytest.mark.parametrize(
    "changes",
    [
        {"worker_factory": "unused:make"},
        {"embedding_dimensions": None},
        {"embedding_model_id": None},
        {"embedding_dimensions": 4097},
    ],
)
def test_invalid_factory_or_model_settings_fail_early(changes):
    values = {"embedding_model_id": "recorded", "embedding_dimensions": 2, **changes}
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://unused/unused_test",
            api_token=TEST_TOKEN,
            integration_factory="unused:make",
            **values,
        )


def test_dimensions_and_empty_compose_options_parse_from_environment(monkeypatch):
    monkeypatch.setenv("CONTEXTBRIDGE_EMBEDDING_DIMENSIONS", "2")
    monkeypatch.setenv("CONTEXTBRIDGE_EMBEDDING_MODEL_ID", "recorded")
    monkeypatch.setenv("CONTEXTBRIDGE_INTEGRATION_FACTORY", "")
    configuration = Settings(
        _env_file=None, database_url="postgresql+psycopg://unused/unused_test", api_token=TEST_TOKEN
    )
    assert configuration.embedding_dimensions == 2 and configuration.integration_factory is None


@pytest.mark.parametrize(
    "field", ["extraction_provider", "formation_verifier", "embedding_backend"]
)
def test_incomplete_backend_pairs_are_rejected(field):
    configuration = settings()
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        assemble(configuration, None, replace(make(configuration, None), **{field: None}))


def test_factory_failures_do_not_echo_exception_chain(monkeypatch):
    secret = "private-provider-configuration"

    def fail(settings, sessions):
        try:
            raise RuntimeError(secret)
        except RuntimeError as cause:
            raise ModuleError("PROVIDER_UNAVAILABLE", retryable=True) from cause

    monkeypatch.setattr("tests.integration.provider_factory.make", fail)
    with pytest.raises(ModuleError) as error:
        load_integration(settings(), None)
    assert error.value.code == "PROVIDER_UNAVAILABLE" and error.value.retryable
    assert secret not in "".join(traceback.format_exception(error.value))


def test_retrieval_only_assembly_has_no_fake_embedding_or_extraction():
    configuration = Settings(
        _env_file=None, database_url="postgresql+psycopg://unused/unused_test", api_token=TEST_TOKEN
    )
    providers = assemble(configuration, None, IntegrationBackends())
    assert providers.embedder is None and providers.modules.extractor is None
    assert providers.modules.admission is None and providers.modules.consolidator is None


def test_cloudflare_runtime_assembles_without_a_factory_or_model_calls():
    from contextbridge.background.runtime import load_providers
    from contextbridge.retrieval.cloudflare import CloudflareEmbeddingBackend
    from tests.retrieval.test_cloudflare import configuration

    configured = configuration()
    providers = load_integration(configured, None)
    assert isinstance(providers.embedder.backend, CloudflareEmbeddingBackend)
    assert load_providers(configured, None).embedder.dimensions == 1024
    assert providers.modules.extractor is None and providers.modules.consolidator is None
    assert providers.modules.retriever.config.embedding_model_id == configured.embedding_model_id


@pytest.mark.parametrize("supplied", [True, False])
def test_cloudflare_fills_only_missing_embedding_backend(monkeypatch, supplied):
    from tests.retrieval.test_cloudflare import configuration

    configured = configuration(integration_factory="tests.integration.provider_factory:make")
    original = make(configured, None)
    backends = original if supplied else replace(original, embedding_backend=None)
    monkeypatch.setattr("tests.integration.provider_factory.make", lambda *_: backends)
    providers = load_integration(configured, None)
    assert providers.modules.extractor.provider is original.extraction_provider
    if supplied:
        assert providers.embedder.backend is original.embedding_backend
    else:
        assert providers.embedder.backend is not None


def test_hosted_formation_is_opt_in_and_execution_state_is_fresh(monkeypatch):
    from tests.formation.test_groq_provider import settings as formation_settings

    monkeypatch.setattr(
        "contextbridge.formation.providers.config.load_settings", formation_settings
    )
    configuration = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused/unused_test",
        api_token=TEST_TOKEN,
        formation_enabled=True,
    )
    providers = load_integration(configuration, None)
    first, second = providers.fresh(), providers.fresh()
    assert first.modules.extractor.provider is not second.modules.extractor.provider
    assert first.modules.extractor.verifier is first.modules.admission.verifier
    assert first.modules.admission.verifier is not second.modules.admission.verifier
    assert first.modules.resolution.interpreter.client is first.modules.extractor.provider.client
    assert first.modules.retriever.config.expand_graph
    assert first.modules.retriever.config.verify_types == frozenset({"DECISION"})
    assert first.modules.extractor.provider.client.calls == []


def test_evidence_v2_adapters_share_guarded_client_but_not_task_state(monkeypatch):
    from contextbridge.evidence_time.runtime import BundleAwareExtractor, BundleAwareVerifier
    from tests.formation.test_groq_provider import settings as formation_settings

    monkeypatch.setattr(
        "contextbridge.formation.providers.config.load_settings", formation_settings
    )
    configuration = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused/unused_test",
        api_token=TEST_TOKEN,
        formation_enabled=True,
        capture_evidence_v2_enabled=True,
    )
    providers = load_integration(configuration, None)
    first, second = providers.fresh(), providers.fresh()
    extractor = first.modules.extractor
    verifier = first.modules.admission.verifier
    assert isinstance(extractor, BundleAwareExtractor)
    assert isinstance(verifier, BundleAwareVerifier)
    assert extractor.client is extractor.legacy.provider.client is verifier.client
    assert extractor.provider is not second.modules.extractor.provider
    assert extractor.client is not second.modules.extractor.client
    assert extractor.client.calls == []


def test_semantic_compaction_has_fresh_separate_single_request_client(monkeypatch):
    from tests.formation.test_groq_provider import settings as formation_settings

    monkeypatch.setattr(
        "contextbridge.formation.providers.config.load_settings", formation_settings
    )
    configuration = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused/unused_test",
        api_token=TEST_TOKEN,
        formation_enabled=True,
    )
    providers = load_integration(configuration, None)
    first, second = providers.fresh(), providers.fresh()
    assert first.compaction_verifier is not second.compaction_verifier
    client = first.compaction_verifier.client
    assert client is not first.modules.extractor.provider.client
    assert client.max_calls == 1 and client.calls == []
    assert second.compaction_verifier.client.calls == []
