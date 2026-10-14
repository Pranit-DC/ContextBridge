"""Bounded synthetic connectivity/relevance check; never reads stored memories."""

import argparse
import json
import math
import os
from dataclasses import asdict
from pathlib import Path

from contextbridge.config import Settings
from contextbridge.formation.providers.chat import ChatClient
from contextbridge.formation.providers.config import FormationSettings
from contextbridge.formation.providers.interpretation import ChatSearchEvidenceJudge
from contextbridge.retrieval.cloudflare import CloudflareEmbeddingBackend
from scripts.v1.budget import BudgetTransport, Ledger


def cosine(left, right):
    denominator = math.sqrt(sum(x * x for x in left) * sum(x * x for x in right))
    return sum(x * y for x, y in zip(left, right, strict=True)) / denominator if denominator else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--free-groq-confirmed", action="store_true", required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Choose a new report path; existing verification evidence is preserved.")
    settings = Settings()
    if settings.embedding_provider != "cloudflare":
        parser.error("Configure Cloudflare embeddings before checking the live providers.")
    formation = FormationSettings().model_copy(
        update={
            "allow_hosted": True,
            "allow_paid": False,
            "groq_free_plan_confirmed": args.free_groq_confirmed,
            "max_output_tokens": 1024,
        }
    )
    formation.check_execution()
    if not formation.is_groq_free():
        parser.error("The configured provider must be the confirmed Free Groq account.")
    args.ledger = args.ledger.resolve()
    ledger = Ledger(args.ledger)
    if ledger.snapshot()["stopped"] or any(ledger.snapshot()["calls"].values()):
        parser.error("This check ledger is already used. Preserve it; do not resume or reset it.")
    # Claim the entire check atomically, not just each HTTP call. Two simultaneous
    # launches must not both observe an empty ledger and exceed the three-call ceiling.
    try:
        claim = os.open(str(args.ledger) + ".started", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        parser.error("This check is already claimed. Preserve its ledger and report.")
    else:
        os.close(claim)
    report = {"before": ledger.snapshot(), "checks": []}
    try:
        client = ChatClient(formation, transport=BudgetTransport(args.ledger, "groq"))
        judgment = ChatSearchEvidenceJudge(client).judge(
            "The example project uses PostgreSQL.", "The example project uses PostgreSQL."
        )
        report["checks"].append(
            {
                "name": "groq_structured_evidence",
                "judgment": judgment,
                "observation": asdict(client.last_observation),
            }
        )
        backend = CloudflareEmbeddingBackend(
            api_key=settings.embedding_api_key.get_secret_value(),
            base_url=settings.embedding_base_url.get_secret_value(),
            model_id=settings.embedding_model_id,
            dimensions=settings.embedding_dimensions,
            transport=BudgetTransport(args.ledger, "cloudflare"),
        )
        documents = [
            "The example project uses PostgreSQL as its primary database.",
            "I prefer concise answers in Marathi.",
            "API requests require an access token.",
        ]
        queries = [
            "Which database did we choose?",
            "Who is Donald Trump?",
            "What language do I prefer for replies?",
            "How should I bake a chocolate cake?",
            "What is needed to call the API?",
        ]
        vectors = backend.embed_batch(documents)
        questions = backend.embed_query_batch(queries)
        similarities = [[round(cosine(q, d), 4) for d in vectors] for q in questions]
        report["checks"].append(
            {
                "name": "cloudflare_relevance",
                "dimensions": len(vectors[0]),
                "documents": documents,
                "queries": queries,
                "similarities": similarities,
                "configured_min_similarity": settings.retrieval_min_similarity,
            }
        )
    except Exception as error:
        ledger.stop()
        report["failure"] = getattr(error, "code", "CONFIGURATION_OR_PROVIDER_UNAVAILABLE")
    report["after"] = ledger.snapshot()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 1 if "failure" in report else 0


if __name__ == "__main__":
    raise SystemExit(main())
