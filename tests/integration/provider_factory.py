"""Synthetic recorded backends for integration checks; never production defaults."""

import json
from uuid import UUID, uuid5

from contextbridge.runtime import IntegrationBackends


class RecordedExtraction:
    def generate(self, event):
        message = event["messages"][0]
        if message["content"] != "Use PostgreSQL database.":
            return "[]"
        return json.dumps(
            [
                {
                    "schema_version": 1,
                    "candidate_id": str(uuid5(UUID(event["event_id"]), "decision")),
                    "event_id": event["event_id"],
                    "scope": event["scope"],
                    "project_id": event["project_id"],
                    "type": "DECISION",
                    "content": message["content"],
                    "conditions": {},
                    "valid_from": event["occurred_at"],
                    "claim_key": "project.database.primary",
                    "confidence": 0.95,
                    "usefulness": 0.95,
                    "source": {
                        "kind": "user",
                        "agent": event["agent"],
                        "session": event["session"],
                        "interaction": event["interaction"],
                        "evidence": message["content"],
                    },
                    "evidence_refs": [
                        {"event_id": event["event_id"], "message_id": message["message_id"]}
                    ],
                }
            ]
        )


class RecordedSupport:
    def verify(self, candidate, event):
        return "supported" if candidate["content"] == "Use PostgreSQL database." else "uncertain"


class RecordedEmbedding:
    def embed_batch(self, texts):
        return [[0.0, 1.0] if "SQLite" in text else [1.0, 0.0] for text in texts]


class RecordedJudge:
    def judge(self, claim, evidence):
        return "supports" if claim == evidence else "insufficient"


def make(settings, sessions):
    return IntegrationBackends(
        extraction_provider=RecordedExtraction(),
        formation_verifier=RecordedSupport(),
        embedding_backend=RecordedEmbedding(),
        evidence_judge=RecordedJudge(),
    )
