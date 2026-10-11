"""Test-only substitutes for Om and Harshal's independently developed modules."""

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "docs" / "team-plan" / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeExtractor:
    def __init__(self):
        self.calls = []

    def extract(self, event):
        self.calls.append(event)
        return [fixture("candidate")]


class FakeRetriever:
    def search(self, query, repository, embedder, verifier):
        return fixture("retrieval-result")


class FakeRepository:
    def __init__(self, *, live=True):
        self.live = live
        self.checks = []

    def is_live(self, version_id, query):
        self.checks.append((version_id, query))
        return self.live
