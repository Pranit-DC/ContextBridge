from contextbridge.contracts import RetrievalResult
from contextbridge.engine.context_budget import encoded_size
from tests.integration.retrieval_fakes import RecordedRetriever, create, query
from tests.integration.test_retrieval_api import api


def test_rich_endpoint_compacts_after_validation_and_preserves_full_inspection(database):
    content = "Database SQLite for tests only. " * 100 + "Not production; 64 MB, since 2026-10-14."
    memory = create(database, content=content)
    with api(database, RecordedRetriever()) as client:
        response = client.post("/v1/retrieval/search", json=query()).json()
        assert encoded_size(RetrievalResult.model_validate(response)) <= 12_000
        assert "CONTEXT_CONTENT_OMITTED" in response["warnings"]
        assert "Full claim omitted" in response["cards"][0]["content"]
        inspected = client.get(f"/v1/memories/{memory.id}").json()
        assert inspected["memory"]["version"]["content"] == content
        legacy = client.post(
            "/v1/memories/search",
            json={"scope": "project", "project_id": "contextbridge", "query": "database"},
        ).json()
        assert legacy[0]["version"]["content"] == content
