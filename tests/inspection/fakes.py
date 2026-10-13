"""Fake service responses for the viewer. They prove client/viewer behavior, not the real API."""

import json
from collections.abc import Callable
from uuid import uuid4

import httpx

TOKEN = "viewer-test-token-0123456789abcdef"
URL = "http://127.0.0.1:8000"
PROJECT = "contextbridge"


def version(
    content="ContextBridge uses PostgreSQL as its primary database.",
    *,
    number=1,
    status="ACTIVE",
    valid_from="2026-10-09T10:00:00Z",
    valid_to=None,
    evidence="For ContextBridge, use PostgreSQL. This is our agreed project decision.",
    agent="codex-pranit",
) -> dict:
    return {
        "id": str(uuid4()),
        "number": number,
        "content": content,
        "status": status,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "recorded_at": valid_from,
        "source": {
            "kind": "user",
            "agent": agent,
            "session": "session-1",
            "interaction": f"interaction-{number}",
            "evidence": evidence,
        },
    }


def memory(
    content="ContextBridge uses PostgreSQL as its primary database.",
    *,
    scope="project",
    project_id=PROJECT,
    conditions=None,
    type_="DECISION",
    number=1,
    memory_id=None,
    **version_kwargs,
) -> dict:
    return {
        "id": memory_id or str(uuid4()),
        "scope": scope,
        "project_id": project_id if scope == "project" else None,
        "type": type_,
        "conditions": conditions or {},
        "created_at": "2026-10-09T10:00:01Z",
        "current_version": number,
        "version": version(content, number=number, **version_kwargs),
    }


def inspection(mem: dict, history: list[dict] | None = None, edges: list[dict] | None = None):
    return {"memory": mem, "history": history or [mem["version"]], "edges": edges or []}


def record(mem: dict, *, decision_state="clear", confidence=0.9, claim_key=None) -> dict:
    return {
        "memory": mem,
        "claim_key": claim_key,
        "confidence": confidence,
        "decision_state": decision_state,
    }


def browse_result(*mems: dict, next_cursor=None, **record_kwargs) -> dict:
    return {
        "schema_version": 1,
        "items": [record(m, **record_kwargs) for m in mems],
        "next_cursor": next_cursor,
    }


def retrieval_result(*mems, degraded=False, warnings=None):
    return {
        "schema_version": 1,
        "degraded": degraded,
        "warnings": warnings or [],
        "cards": [
            {
                "memory_id": m["id"],
                "version_id": m["version"]["id"],
                "version_number": m["current_version"],
                "type": m["type"],
                "content": m["version"]["content"],
                "scope": m["scope"],
                "project_id": m["project_id"],
                "conditions": m["conditions"],
                "valid_from": m["version"]["valid_from"],
                "valid_to": m["version"]["valid_to"],
                "decision_state": "clear",
                "verification": "not_requested",
                "source_ref": {
                    k: m["version"]["source"][k] for k in ("agent", "session", "interaction")
                },
            }
            for m in mems
        ],
    }


def update_body(expected_version=1, content="ContextBridge uses SQLite.") -> dict:
    return {
        "expected_version": expected_version,
        "content": content,
        "source": {
            "kind": "user",
            "agent": "viewer",
            "session": "viewer-session",
            "interaction": "viewer-correction",
            "evidence": "Corrected by the user in the viewer.",
        },
    }


class FakeService:
    """An httpx transport that serves canned responses and records every request."""

    def __init__(self):
        self.routes: dict[tuple[str, str], Callable[[httpx.Request], httpx.Response]] = {}
        self.requests: list[httpx.Request] = []

    def on(self, method: str, path: str, response=None, *, status=200, body=None):
        if response is None:

            def response(_request, _status=status, _body=body):
                if _body is None and _status == 204:
                    return httpx.Response(204)
                return httpx.Response(_status, json=_body)

        self.routes[(method, path)] = response
        return self

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        route = self.routes.get((request.method, request.url.path))
        if route is None:
            return httpx.Response(404, json={"detail": "Not found"})
        return route(request)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def calls(self) -> list[tuple[str, str]]:
        return [(r.method, r.url.path) for r in self.requests]

    def json_of(self, index: int):
        return json.loads(self.requests[index].content)
