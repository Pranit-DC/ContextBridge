import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from contextbridge.api import create_app
from contextbridge.config import Settings
from contextbridge.engine.modules import ModuleGateway
from contextbridge.service import MemoryService
from tests.conftest import TEST_TOKEN
from tests.integration.retrieval_fakes import RecordedRetriever, create, query

pytestmark = pytest.mark.integration


def api(database, retriever=None):
    settings = Settings(
        _env_file=None, database_url=database[0], developer_id="developer-a", api_token=TEST_TOKEN
    )
    return TestClient(
        create_app(settings, modules=ModuleGateway(retriever=retriever)),
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )


def test_new_search_is_authenticated_and_disabled_without_real_injection(database):
    with api(database) as client:
        response = client.post("/v1/retrieval/search", json=query())
        assert response.status_code == 503
        assert response.json()["detail"] == {"code": "PROVIDER_UNAVAILABLE", "retryable": False}
        unauthorized = client.post(
            "/v1/retrieval/search", json=query(), headers={"Authorization": "Bearer invalid"}
        )
        assert unauthorized.status_code == 401
        invalid = client.post(
            "/v1/retrieval/search", json=query(conditions={"password": "private-value"})
        )
        assert invalid.status_code == 422 and "private-value" not in invalid.text
        assert client.post("/v1/retrieval/search", json=query(limit=21)).status_code == 422


def test_injected_retriever_reads_store_and_reports_missing_embeddings(database):
    target = create(database)
    create(database, project_id="other-project")
    with api(database, RecordedRetriever()) as client:
        response = client.post("/v1/retrieval/search", json=query())
        assert response.status_code == 200
        result = response.json()
        assert [card["memory_id"] for card in result["cards"]] == [str(target.id)]
        assert result["degraded"] is True and result["warnings"] == ["EMBEDDING_UNAVAILABLE"]
        assert result["cards"][0]["verification"] == "not_requested"


def test_forged_content_with_a_live_version_is_rejected(database):
    create(database)

    class ForgingRetriever(RecordedRetriever):
        def search(self, *args):
            result = super().search(*args)
            result["cards"][0]["content"] = "Forged private content"
            return result

    with api(database, ForgingRetriever()) as client:
        response = client.post("/v1/retrieval/search", json=query())
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "INVALID_PROVIDER_OUTPUT"
        assert "Forged" not in response.text


def test_forget_during_retrieval_cannot_return_a_stale_card(database):
    target = create(database)

    class ForgettingRetriever(RecordedRetriever):
        def search(self, *args):
            result = super().search(*args)
            with Session(database[1]) as session:
                MemoryService(session, "developer-a").forget(target.id)
            return result

    with api(database, ForgettingRetriever()) as client:
        response = client.post("/v1/retrieval/search", json=query())
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "INVALID_PROVIDER_OUTPUT"
        assert target.version.content not in response.text
