import asyncio
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from contextbridge.api import create_app
from contextbridge.config import Settings
from contextbridge.engine.http import MAX_CAPTURE_BODY_BYTES, CaptureBodyLimit
from tests.conftest import TEST_TOKEN
from tests.engine.fakes import fixture


def unavailable_settings(**changes):
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:private-db-password@127.0.0.1:1/missing?connect_timeout=1",
        api_token=TEST_TOKEN,
        **changes,
    )


def test_disabled_ingestion_and_status_fail_before_database_access():
    with TestClient(
        create_app(unavailable_settings()), headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    ) as client:
        response = client.post("/v1/interactions", json=fixture("captured-event"))
        assert response.status_code == 503
        assert response.json() == {"detail": {"code": "PROVIDER_UNAVAILABLE", "retryable": False}}
        assert client.get(f"/v1/jobs/{uuid4()}").json() == response.json()


def test_storage_outage_is_retryable_and_omits_database_exception():
    with TestClient(
        create_app(unavailable_settings(capture_project_id="contextbridge")),
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    ) as client:
        response = client.post("/v1/interactions", json=fixture("captured-event"))
        assert response.status_code == 503
        assert response.json() == {"detail": {"code": "STORAGE_UNAVAILABLE", "retryable": True}}
        assert "private-db-password" not in response.text
        assert client.get("/health/live").status_code == 200


def test_invalid_json_unknown_fields_and_job_ids_return_safe_codes():
    with TestClient(
        create_app(unavailable_settings()), headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    ) as client:
        for content in ['{"password":"private-value",', json.dumps({"unknown": "private-value"})]:
            response = client.post(
                "/v1/interactions", content=content, headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 422
            assert response.json()["detail"]["code"] == "INVALID_INPUT"
            assert "private-value" not in response.text
        assert client.get("/v1/jobs/not-a-uuid").status_code == 422


def test_oversized_http_body_is_rejected_before_json_parsing():
    with TestClient(create_app(unavailable_settings())) as client:
        response = client.post("/v1/interactions", content="x" * (MAX_CAPTURE_BODY_BYTES + 1))
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_INPUT"


def test_chunked_request_without_content_length_is_bounded():
    async def exercise():
        calls = []
        sent = []
        chunks = iter(
            [
                {
                    "type": "http.request",
                    "body": b"x" * (MAX_CAPTURE_BODY_BYTES // 2),
                    "more_body": True,
                },
                {
                    "type": "http.request",
                    "body": b"x" * (MAX_CAPTURE_BODY_BYTES // 2 + 1),
                    "more_body": False,
                },
            ]
        )

        async def downstream(scope, receive, send):
            calls.append(True)

        async def receive():
            return next(chunks)

        async def send(message):
            sent.append(message)

        await CaptureBodyLimit(downstream)(
            {"type": "http", "path": "/v1/interactions"}, receive, send
        )
        assert calls == []
        assert sent[0]["status"] == 422

    asyncio.run(exercise())


@pytest.mark.parametrize("binding", [None, ""])
def test_empty_optional_binding_keeps_base_api_configurable(binding):
    assert unavailable_settings(capture_project_id=binding).capture_project_id is None
