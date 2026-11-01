"""Actual hosted adapters with the one shared synthetic verification ledger."""

import os
from dataclasses import replace

from sqlalchemy.engine import make_url

from contextbridge.retrieval.cloudflare import CloudflareEmbeddingBackend
from contextbridge.runtime import hosted_backends
from scripts.v1.budget import BudgetTransport


def make(settings, sessions):
    url = make_url(settings.database_url.get_secret_value())
    ledger = os.environ.get("CONTEXTBRIDGE_V1_DEMO_LEDGER")
    if (
        url.host != "127.0.0.1"
        or url.database != "contextbridge_v1_live_test"
        or not settings.developer_id.startswith("v1-demo-")
        or settings.capture_project_id != "v1-synthetic-demo"
        or not ledger
    ):
        raise ValueError("ISOLATED_DEMO_REQUIRED")
    backends = hosted_backends(settings, sessions)
    backends.extraction_provider.client.transport = BudgetTransport(ledger, "groq")
    backends.evidence_judge.client.transport = BudgetTransport(ledger, "groq")
    if backends.context_evidence_judge is not None:
        backends.context_evidence_judge.client.transport = BudgetTransport(ledger, "groq")
    backend = CloudflareEmbeddingBackend(
        api_key=settings.embedding_api_key.get_secret_value(),
        base_url=settings.embedding_base_url.get_secret_value(),
        model_id=settings.embedding_model_id,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.provider_timeout_seconds,
        transport=BudgetTransport(ledger, "cloudflare"),
    )
    return replace(backends, embedding_backend=backend)
