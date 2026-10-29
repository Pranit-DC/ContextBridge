"""Viewer automation uses synthetic authentication and mocked transport only."""

import os

import httpx
import pytest


@pytest.fixture(autouse=True)
def isolated_viewer_environment(monkeypatch):
    for name in os.environ:
        if name.startswith(("CONTEXTBRIDGE_FORMATION_", "CONTEXTBRIDGE_EMBEDDING_")) or name in (
            "CONTEXTBRIDGE_API_TOKEN",
            "CONTEXTBRIDGE_PROJECT_ID",
        ):
            monkeypatch.delenv(name, raising=False)

    def no_network(*args, **kwargs):
        pytest.fail("Viewer automation must inject a mocked transport")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)
