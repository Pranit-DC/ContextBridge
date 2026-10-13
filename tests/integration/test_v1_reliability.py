from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from contextbridge.api import create_app
from contextbridge.config import Settings
from contextbridge.inspection.client import HttpViewerClient, ViewerSettings
from contextbridge.inspection.controller import ViewerController
from tests.conftest import TEST_TOKEN

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "content,evidence,type_",
    [
        (
            "API calls require token access.",
            "I confirm that we need token access for API call",
            "FACT",
        ),
        ("I prefer explanations in Marathi.", "I prefer explanations in Marathi.", "PREFERENCE"),
        ("The launch meeting is Friday.", "We agreed that the launch meeting is Friday.", "EVENT"),
        (
            "Retry failed network requests at most twice.",
            "We decided to retry failed network requests at most twice.",
            "DECISION",
        ),
        ("मला मराठीत उत्तर हवे आहे.", "मला मराठीत उत्तर हवे आहे.", "PREFERENCE"),
        ("Use the path src/example_v2.py.", "The selected file is src/example_v2.py.", "FACT"),
    ],
)
def test_arbitrary_explicit_saves_through_viewer_and_real_api(database, content, evidence, type_):
    settings = Settings(_env_file=None, database_url=database[0], api_token=TEST_TOKEN)
    with TestClient(create_app(settings)) as api:

        def forward(request):
            result = api.request(
                request.method, request.url.path, headers=request.headers, content=request.content
            )
            return httpx.Response(result.status_code, content=result.content)

        viewer = ViewerController(
            HttpViewerClient(
                ViewerSettings(token=TEST_TOKEN), "reliability", httpx.MockTransport(forward)
            )
        )
        saved = viewer.save(str(uuid4()), content, evidence, type_)
        assert saved.ok, saved.notice
        inspected = viewer.open(saved.data["id"])
        assert inspected.detail.current.content == content
        assert inspected.detail.current.evidence == evidence
        assert viewer.forget(saved.data["id"], True).ok


def test_recent_processing_is_owner_and_project_bound(database):
    from tests.integration.write_fakes import Harness

    first = Harness(database)
    job, _, _ = first.enqueue("The first fact.")
    second = Harness(database, owner="another-owner")
    other, _, _ = second.enqueue("Private other-owner fact.")
    with first.client() as api:
        result = api.get("/v1/jobs", params={"project_id": "contextbridge"})
        assert result.status_code == 200
        assert [r["job_id"] for r in result.json()] == [str(job)]
        assert str(other) not in result.text and "Private" not in result.text
        assert api.get("/v1/jobs", params={"project_id": "another-project"}).status_code == 404
        assert (
            api.get(
                "/v1/jobs",
                params={"project_id": "contextbridge"},
                headers={"Authorization": "Bearer wrong"},
            ).status_code
            == 401
        )


def test_unrelated_keyless_candidate_can_be_saved_with_existing_same_type(database):
    from tests.integration.write_fakes import Harness

    harness = Harness(database)
    old, _, _ = harness.enqueue("Use PostgreSQL.")
    assert harness.process(old).status == "succeeded"
    harness.settings = harness.settings.model_copy(update={"formation_enabled": True})
    harness.set_relation("unrelated")
    new, _, _ = harness.enqueue("API calls require token access.", claim_key=None)
    result = harness.process(new)
    assert result.status == "succeeded" and len(result.memory_ids) == 1
