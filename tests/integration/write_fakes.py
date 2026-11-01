"""Recorded boundary substitutes; not Om's formation module or a production policy."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from contextbridge.api import create_app
from contextbridge.config import Settings
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.resolution import SafeResolutionPolicy
from contextbridge.engine.write import WriteEngine
from tests.conftest import TEST_TOKEN
from tests.engine.fakes import fixture


class ScriptedExtractor:
    def __init__(self):
        self.outputs = {}
        self.calls = []

    def extract(self, event):
        self.calls.append(event["event_id"])
        return deepcopy(self.outputs[event["event_id"]])


class Admit:
    def __init__(self, outcome="ADMIT"):
        self.outcome = outcome

    def assess(self, candidate, context):
        return {
            "schema_version": 1,
            "candidate_id": candidate["candidate_id"],
            "outcome": self.outcome,
            "reason_codes": ["EXPLICIT_DECISION"],
        }


class Relation:
    def __init__(self, relation):
        self.relation = relation

    def compare(self, candidate, record):
        return self.relation


class Harness:
    def __init__(
        self,
        database,
        *,
        owner="developer-a",
        project="contextbridge",
        admission=None,
        resolution=None,
        **settings,
    ):
        self.database = database
        self.settings = Settings(
            _env_file=None,
            database_url=database[0],
            api_token=TEST_TOKEN,
            developer_id=owner,
            capture_project_id=project,
            **settings,
        )
        self.extractor = ScriptedExtractor()
        self.modules = ModuleGateway(
            extractor=self.extractor, admission=admission or Admit(), resolution=resolution
        )

    @contextmanager
    def client(self):
        with TestClient(
            create_app(self.settings, modules=self.modules),
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        ) as client:
            yield client

    def enqueue(
        self,
        content="Use PostgreSQL.",
        *,
        conditions=None,
        time=None,
        project=None,
        evidence=None,
        claim_key="project.database.primary",
        role="user",
    ):
        event = fixture("captured-event")
        event.update(
            event_id=str(uuid4()),
            project_id=project or self.settings.capture_project_id,
            occurred_at=(time or datetime.now(UTC) - timedelta(days=2)).isoformat(),
        )
        event["messages"] = [
            {"message_id": "message-1", "role": role, "content": evidence or content}
        ]
        candidate = fixture("candidate")
        candidate.update(
            candidate_id=str(uuid4()),
            event_id=event["event_id"],
            project_id=event["project_id"],
            content=content,
            conditions=conditions or {},
            valid_from=event["occurred_at"],
            claim_key=claim_key,
        )
        candidate["source"].update(evidence=evidence or content, kind=role)
        candidate["evidence_refs"][0]["event_id"] = event["event_id"]
        self.extractor.outputs[event["event_id"]] = [candidate]
        with self.client() as client:
            accepted = client.post("/v1/interactions", json=event)
        assert accepted.status_code == 202
        return accepted.json()["job_id"], candidate, event

    def process(self, job_id, modules=None):
        from uuid import UUID

        with Session(self.database[1], expire_on_commit=False) as session:
            return WriteEngine(session, self.settings, modules or self.modules).process(
                UUID(job_id)
            )

    def set_relation(self, relation):
        self.modules = ModuleGateway(
            extractor=self.extractor,
            admission=self.modules.admission,
            resolution=SafeResolutionPolicy(Relation(relation)),
        )
