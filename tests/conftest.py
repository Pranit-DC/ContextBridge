import os
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from contextbridge.api import create_app
from contextbridge.config import Settings

TEST_TOKEN = "test-only-token-with-at-least-32-characters"


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
        connection.execute(text("TRUNCATE memory_edges, memory_versions, memories CASCADE"))
    try:
        yield url, engine
    finally:
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE memory_edges, memory_versions, memories CASCADE"))
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
