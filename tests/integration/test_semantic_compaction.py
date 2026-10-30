"""Real API/store with a scripted equivalence boundary; never a hosted quality claim."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from contextbridge.api import create_app
from contextbridge.config import Settings
from contextbridge.models import Memory, VersionProvenance
from tests.conftest import TEST_TOKEN
from tests.integration.test_compaction import plan, save

pytestmark = pytest.mark.integration
PATH = "/v1/maintenance/compact-semantic"


class Verifier:
    def __init__(self):
        self.calls = 0
        self.guard = None
        self.before = lambda: None
        self.change = lambda checks: checks

    def bind_guard(self, guard):
        self.guard = guard

    def verify(self, records):
        self.calls += 1
        self.before()
        self.guard()  # The production quota client calls this after any quota wait.
        checks = [
            {"memory_id": r["memory"]["id"], "relation": "equivalent", "both_supported": True}
            for r in records[1:]
        ]
        return self.change({"checks": checks})


@contextmanager
def api(database, verifier, owner="developer-a"):
    settings = Settings(
        _env_file=None, database_url=database[0], api_token=TEST_TOKEN, developer_id=owner
    )
    with TestClient(
        create_app(settings, compaction_verifier=verifier),
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    ) as client:
        yield client


def examples(client):
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    return (
        save(client, content="Use PostgreSQL for this project.", valid_from=past),
        save(client, content="The project database is PostgreSQL.", valid_from=past),
    )


def verified(client, body):
    response = client.post(PATH, json=body | {"allow_online_verification": True})
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client, body, preview):
    return client.post(
        PATH,
        json=body
        | {
            "confirm": True,
            "plan_revision": preview["plan_revision"],
            "verification_token": preview["verification_token"],
        },
    )


def test_paraphrase_preview_confirm_history_restore_forget_and_exact_route_unchanged(database):
    verifier = Verifier()
    with api(database, verifier) as client:
        keep, duplicate = examples(client)
        body = plan(keep, duplicate)
        assert client.post("/v1/maintenance/compact", json=body).status_code == 409
        assert client.post(PATH, json=body).status_code == 409 and verifier.calls == 0
        preview = verified(client, body)
        assert not preview["applied"] and verifier.calls == 1
        assert client.get(f"/v1/memories/{duplicate['id']}/lifecycle").json()["retired_at"] is None
        assert confirm(client, body, preview).status_code == 200 and verifier.calls == 1
        history = client.get(f"/v1/memories/{duplicate['id']}").json()["history"]
        assert history[0]["source"] == duplicate["version"]["source"]
        assert history[0]["content"] == duplicate["version"]["content"]
        assert confirm(client, body, preview).status_code == 409
        from tests.test_validation import payload

        assert (
            client.post(
                f"/v1/memories/{duplicate['id']}/restore",
                json={
                    "scope": "project",
                    "project_id": "contextbridge",
                    "expected_version": 1,
                    "source_version": 1,
                    "source": payload()["source"],
                },
            ).status_code
            == 200
        )
        assert client.delete(f"/v1/memories/{duplicate['id']}").status_code == 204
        assert client.get(f"/v1/memories/{keep['id']}").status_code == 200


@pytest.mark.parametrize(
    "defect",
    ["different", "uncertain", "unsupported", "missing", "duplicate", "foreign", "extra", "error"],
)
def test_rejected_or_malformed_verdict_never_retires(database, defect):
    verifier = Verifier()

    def change(result):
        check = result["checks"][0]
        if defect in ("different", "uncertain"):
            check["relation"] = defect
        elif defect == "unsupported":
            check["both_supported"] = False
        elif defect == "missing":
            result["checks"] = []
        elif defect == "duplicate":
            result["checks"].append(check.copy())
        elif defect == "foreign":
            check["memory_id"] = str(uuid4())
        elif defect == "extra":
            check["raw_private_input"] = "synthetic-rejected-value"
        else:
            raise RuntimeError("synthetic-provider-secret")
        return result

    verifier.change = change
    with api(database, verifier) as client:
        keep, duplicate = examples(client)
        response = client.post(PATH, json=plan(keep, duplicate, allow_online_verification=True))
        assert response.status_code in (409, 503)
        assert "synthetic-" not in response.text
        assert client.get(f"/v1/memories/{duplicate['id']}/lifecycle").json()["retired_at"] is None


@pytest.mark.parametrize(
    "defect",
    [
        "owner",
        "project",
        "version",
        "changed",
        "expired",
        "tampered",
        "restart",
        "forgotten",
        "selection",
    ],
)
def test_confirmation_token_binds_owner_plan_freshness_and_server_key(
    database, defect, monkeypatch
):
    from contextbridge.engine import semantic_compaction as module
    from tests.test_validation import payload

    verifier = Verifier()
    with api(database, verifier) as client:
        keep, duplicate = examples(client)
        body = plan(keep, duplicate)
        preview = verified(client, body)
        if defect == "owner":
            with api(database, verifier, owner="other-owner") as other:
                assert confirm(other, body, preview).status_code == 404
            return
        if defect == "project":
            body["project_id"] = "another-project"
        elif defect == "version":
            body["retire"][0]["expected_version"] = 2
        elif defect == "changed":
            assert (
                client.put(
                    f"/v1/memories/{duplicate['id']}",
                    json={
                        "expected_version": 1,
                        "content": "Use SQLite.",
                        "source": payload()["source"],
                    },
                ).status_code
                == 200
            )
        elif defect == "expired":
            original = module.time.time
            now = original()
            monkeypatch.setattr(module.time, "time", lambda: now + 601)
        elif defect == "tampered":
            preview["verification_token"] = "A" + preview["verification_token"][1:]
        elif defect == "restart":
            client.app.state.compaction_signing_key = b"different-key"
        elif defect == "forgotten":
            assert client.delete(f"/v1/memories/{duplicate['id']}").status_code == 204
        elif defect == "selection":
            body = plan(duplicate, keep)
        assert confirm(client, body, preview).status_code in (404, 409)
        assert verifier.calls == 1
        assert client.get(f"/v1/memories/{keep['id']}/lifecycle").json()["retired_at"] is None


def test_forget_during_quota_wait_blocks_request_and_cannot_resurrect(database):
    verifier = Verifier()
    with api(database, verifier) as client:
        keep, duplicate = examples(client)
        verifier.before = lambda: client.delete(f"/v1/memories/{duplicate['id']}")
        response = client.post(PATH, json=plan(keep, duplicate, allow_online_verification=True))
        assert response.status_code == 503
        assert client.get(f"/v1/memories/{duplicate['id']}").status_code == 404
        assert client.get(f"/v1/memories/{keep['id']}/lifecycle").json()["retired_at"] is None


def test_foreground_write_during_provider_wait_and_recheck_after_model(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from tests.test_validation import payload

    verifier = Verifier()
    entered, release = Event(), Event()

    def wait():
        entered.set()
        assert release.wait(10)

    verifier.before = wait
    with api(database, verifier) as client:
        keep, duplicate = examples(client)
        with ThreadPoolExecutor(max_workers=1) as pool:
            task = pool.submit(
                client.post, PATH, json=plan(keep, duplicate, allow_online_verification=True)
            )
            try:
                assert entered.wait(3)
                assert (
                    client.put(
                        f"/v1/memories/{duplicate['id']}",
                        json={
                            "expected_version": 1,
                            "content": "Use SQLite.",
                            "source": payload()["source"],
                        },
                    ).status_code
                    == 200
                )
            finally:
                release.set()
            assert task.result(timeout=5).status_code == 503


def test_semantic_summary_cleanup_failure_is_atomic(database, monkeypatch):
    from contextbridge.engine import semantic_compaction as module

    verifier = Verifier()
    with api(database, verifier) as client:
        keep, duplicate = examples(client)
        body = plan(keep, duplicate)
        preview = verified(client, body)
        original = module.retire_set

        from contextbridge.service import MemoryServiceError

        def cleanup(*args):
            original(*args)
            raise MemoryServiceError(503, "Cleanup unavailable")

        monkeypatch.setattr(module, "retire_set", cleanup)
        assert confirm(client, body, preview).status_code == 503
        with Session(database[1]) as session:
            assert session.get(Memory, UUID(duplicate["id"])).retired_at is None


def test_v2_different_temporal_contracts_are_not_merged(database):
    verifier = Verifier()
    with api(database, verifier) as client:
        keep, duplicate = examples(client)
        with Session(database[1]) as session:
            session.add(
                VersionProvenance(
                    version_id=UUID(duplicate["version"]["id"]),
                    metadata_json={"temporal": {"precision": "day"}},
                )
            )
            session.commit()
        assert (
            client.post(
                PATH, json=plan(keep, duplicate, allow_online_verification=True)
            ).status_code
            == 409
        )
        assert verifier.calls == 0


def test_workspace_semantic_preview_confirmation_uses_actual_guarded_chat_adapter(
    database, tmp_path, monkeypatch
):
    import json

    import httpx
    from streamlit.testing.v1 import AppTest

    from contextbridge.engine.semantic_compaction import ChatCompactionVerifier
    from contextbridge.formation.providers.bounded import QuotaClient
    from contextbridge.formation.providers.quota import TokenGate
    from contextbridge.inspection.client import HttpViewerClient, ViewerSettings
    from contextbridge.inspection.controller import ViewerController
    from tests.formation.test_groq_provider import settings as formation_settings
    from tests.test_local_workspace import APP, button

    requests = []

    def hosted(request):
        body = json.loads(request.content)
        data = json.loads(body["messages"][1]["content"])
        requests.append(data)
        assert "own USER/TOOL evidence" in body["messages"][0]["content"]
        assert data["keeper"]["memory"]["version"]["source"]["evidence"]
        assert len(data["redundant"]) == 1
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "checks": [
                                        {
                                            "memory_id": data["redundant"][0]["memory"]["id"],
                                            "relation": "equivalent",
                                            "both_supported": True,
                                        }
                                    ]
                                }
                            ),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 40},
            },
        )

    client = QuotaClient(
        formation_settings(max_output_tokens=1024),
        max_calls=1,
        gate=TokenGate(),
        transport=httpx.MockTransport(hosted),
    )
    verifier = ChatCompactionVerifier(client)
    path = tmp_path / ".env"
    path.write_text(
        f"CONTEXTBRIDGE_API_TOKEN='{TEST_TOKEN}'\nCONTEXTBRIDGE_DATABASE_URL='{database[0]}'\n"
    )
    monkeypatch.setenv("CONTEXTBRIDGE_LOCAL_ENV_FILE", str(path))
    monkeypatch.delenv("CONTEXTBRIDGE_API_URL", raising=False)
    with api(database, verifier) as backend:
        keep, duplicate = examples(backend)

        def handle(request):
            response = backend.request(
                request.method,
                request.url.path,
                headers={"Authorization": request.headers["Authorization"]},
                json=json.loads(request.content) if request.content else None,
            )
            return httpx.Response(
                response.status_code,
                content=response.content,
                headers={"content-type": "application/json"},
            )

        def factory(url, token, project):
            return ViewerController(
                HttpViewerClient(
                    ViewerSettings(url, token), project, transport=httpx.MockTransport(handle)
                )
            )

        app = AppTest.from_file(str(APP), default_timeout=15)
        app.session_state["make_controller"] = factory
        app.run()
        app.sidebar.radio(key="workspace_page").set_value("Activity").run()
        button(app, "Review current memories").click().run()
        assert not app.exception
        app.selectbox(key="compact_keep").set_value(keep["id"]).run()
        app.multiselect(key="compact_retire").set_value([duplicate["id"]]).run()
        app.checkbox(key="compact_semantic").check().run()
        assert button(app, "Preview merge").disabled and not requests
        app.checkbox(key="compact_consent").check().run()
        button(app, "Preview merge").click().run()
        assert not app.exception and not app.error, [e.value for e in app.error]
        assert len(requests) == 1
        assert client.calls[0]["reserved_tokens"] <= 8000
        with Session(database[1]) as session:
            assert session.get(Memory, UUID(duplicate["id"])).retired_at is None
        button(app, "Confirm merge").click().run()
        assert not app.exception and not app.error
        assert len(requests) == 1
        with Session(database[1]) as session:
            assert session.get(Memory, UUID(duplicate["id"])).retired_at is not None
            assert session.get(Memory, UUID(keep["id"])).retired_at is None
        assert any("History preserved" in e.value for e in app.success)


def test_source_changed_after_provider_response_is_rechecked_before_preview(database):
    from tests.test_validation import payload

    verifier = Verifier()
    with api(database, verifier) as client:
        keep, duplicate = examples(client)

        def after_response(result):
            assert (
                client.put(
                    f"/v1/memories/{duplicate['id']}",
                    json={
                        "expected_version": 1,
                        "content": "Use SQLite.",
                        "source": payload()["source"],
                    },
                ).status_code
                == 200
            )
            return result

        verifier.change = after_response
        response = client.post(PATH, json=plan(keep, duplicate, allow_online_verification=True))
        assert response.status_code == 409
        assert client.get(f"/v1/memories/{duplicate['id']}/lifecycle").json()["retired_at"] is None


@pytest.mark.parametrize("semantic", [False, True])
def test_equal_text_cannot_hide_different_v2_time_bounds(database, semantic):
    verifier = Verifier()
    with api(database, verifier) as client:
        keep, duplicate = save(client), save(client)
        with Session(database[1]) as session:
            session.add(
                VersionProvenance(
                    version_id=UUID(duplicate["version"]["id"]),
                    metadata_json={"temporal": {"precision": "week"}},
                )
            )
            session.commit()
        route = PATH if semantic else "/v1/maintenance/compact"
        body = plan(keep, duplicate)
        if semantic:
            body["allow_online_verification"] = True
        assert client.post(route, json=body).status_code == 409
        assert verifier.calls == 0


def test_temporal_metadata_change_invalidates_approved_preview(database):
    verifier = Verifier()
    with api(database, verifier) as client:
        keep, duplicate = examples(client)
        ids = [UUID(m["version"]["id"]) for m in (keep, duplicate)]
        with Session(database[1]) as session:
            for identifier in ids:
                session.add(
                    VersionProvenance(
                        version_id=identifier, metadata_json={"temporal": {"precision": "day"}}
                    )
                )
            session.commit()
        body = plan(keep, duplicate)
        preview = verified(client, body)
        with Session(database[1]) as session:
            from sqlalchemy import select

            for row in session.scalars(select(VersionProvenance)):
                row.metadata_json = {"temporal": {"precision": "week"}}
            session.commit()
        assert confirm(client, body, preview).status_code == 409
        assert verifier.calls == 1
