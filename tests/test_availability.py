from fastapi.testclient import TestClient

from contextbridge.api import create_app
from contextbridge.config import Settings
from tests.conftest import TEST_TOKEN


def test_database_outage_is_safe_and_liveness_survives():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:private-db-password@127.0.0.1:1/missing"
        "?connect_timeout=1",
        api_token=TEST_TOKEN,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        assert response.status_code == 503
        assert response.json() == {"detail": "Memory storage unavailable"}
        assert "private-db-password" not in response.text
        assert "psycopg" not in response.text
