from tests.integration.retrieval_fakes import RecordedRetriever, create, query
from tests.integration.test_retrieval_api import api


def test_ambiguous_query_defers_without_repository_or_provider_calls(database):
    class NeverCalled:
        def search(self, *args):
            raise AssertionError("Ambiguous query must not invoke retrieval")

    create(database)
    with api(database, NeverCalled()) as client:
        result = client.post("/v1/retrieval/search", json=query(query="What DB for V1?"))
        assert result.status_code == 200
        assert result.json()["cards"] == []
        assert result.json()["warnings"] == ["QUERY_VERSION_FILTER_REQUIRED"]


def test_explicit_version_filter_stays_authorized_at_real_boundary(database):
    create(database, content="PostgreSQL for V1", conditions={"version": "V1"})
    create(database, content="PostgreSQL for V1", conditions={"version": "V2"})
    with api(database, RecordedRetriever()) as client:
        result = client.post(
            "/v1/retrieval/search",
            json=query(query="PostgreSQL for V1", conditions={"version": "V1"}),
        )
        assert result.status_code == 200
        assert [card["conditions"] for card in result.json()["cards"]] == [{"version": "V1"}]
