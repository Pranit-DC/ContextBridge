import os
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from contextbridge.api import create_app
from contextbridge.config import Settings

TEST_TOKEN = "test-only-token-with-at-least-32-characters"


@pytest.fixture(autouse=True)
def isolate_hosted_embedding_credentials(monkeypatch):
    # Settings(_env_file=None) plus these blanks prevents inherited live credentials.
    # Provider tests install a synthetic key/MockTransport explicitly after this fixture.
    for name in ["PROVIDER", "API_KEY", "BASE_URL", "MODEL_ID", "DIMENSIONS"]:
        monkeypatch.setenv(f"CONTEXTBRIDGE_EMBEDDING_{name}", "")
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_ENABLED", "false")
    monkeypatch.setenv("CONTEXTBRIDGE_CONSOLIDATION_ENABLED", "false")


@pytest.fixture(autouse=True)
def isolate_viewer_widget_credentials(request, monkeypatch):
    # AppTest's signed-out cases must not inherit the migration/CI service token.
    # Individual widget tests can still set an environment token explicitly afterwards.
    if request.node.path.name == "test_app.py" and request.node.path.parent.name == "inspection":
        monkeypatch.delenv("CONTEXTBRIDGE_API_TOKEN", raising=False)


@pytest.fixture
def database():
    url = os.getenv("CONTEXTBRIDGE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set CONTEXTBRIDGE_TEST_DATABASE_URL to run PostgreSQL integration tests")
    engine = create_engine(url)
    if not engine.url.database or not engine.url.database.endswith("_test"):
        engine.dispose()
        pytest.fail("Integration tests require a dedicated database ending in _test")
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE provider_quotas, work_items, consolidation_jobs, "
                "embedding_models, reindex_jobs, "
                "capture_jobs, capture_events, "
                "memory_edges, "
                "memory_versions, memories CASCADE"
            )
        )
    try:
        yield url, engine
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE provider_quotas, work_items, consolidation_jobs, "
                    "embedding_models, reindex_jobs, "
                    "capture_jobs, capture_events, "
                    "memory_edges, "
                    "memory_versions, memories CASCADE"
                )
            )
        engine.dispose()


@pytest.fixture
def clients(database):
    url, _ = database
    with ExitStack() as stack:

        def make_client(owner="developer-a"):
            settings = Settings(
                _env_file=None, database_url=url, api_token=TEST_TOKEN, developer_id=owner
            )
            return stack.enter_context(
                TestClient(create_app(settings), headers={"Authorization": f"Bearer {TEST_TOKEN}"})
            )

        yield make_client


@pytest.fixture
def client(clients):
    return clients()
