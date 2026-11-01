"""Browser fixture: real memory API/PostgreSQL, fake OS vault/Docker, zero hosted calls.

Never load outside tests: the reset/launch endpoints intentionally bypass user authentication.
"""

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from contextbridge.api import create_app
from contextbridge.config import Settings
from contextbridge.engine.modules import ModuleGateway
from contextbridge.product.app import create_product_app
from contextbridge.product.services import Services
from contextbridge.product.settings import ProductSettings
from contextbridge.product.vault import NativeVault
from contextbridge.retrieval.retriever import Retriever
from tests.product.test_security import TOKEN, Backend

url = os.environ["CONTEXTBRIDGE_TEST_DATABASE_URL"]
engine = create_engine(url)
if not engine.url.database or not engine.url.database.endswith("_test"):
    raise RuntimeError("Browser tests require a dedicated _test database")
folder = tempfile.TemporaryDirectory(prefix="contextbridge-browser-")
root = Path(folder.name)
(root / ".env").write_text(
    f"CONTEXTBRIDGE_DATABASE_URL='{url}'\nCONTEXTBRIDGE_API_TOKEN='{TOKEN}'\n"
)
(root / "compose.yaml").write_text("services: {}")
(root / ".env.mcp").write_text(f"CONTEXTBRIDGE_API_TOKEN='{TOKEN}'\n")
backend = Backend()
settings = ProductSettings(root / ".env", vault=NativeVault(root, backend=backend))
services = Services(
    settings,
    root,
    runner=lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=b"" if "-q" in a[0] or "-aq" in a[0] else b"[]"
    ),
    endpoint="unix:///synthetic",
)
core = TestClient(
    create_app(
        Settings(
            _env_file=None,
            database_url=url,
            api_token=TOKEN,
            developer_id="browser-fixture",
            capture_project_id="contextbridge",
        ),
        modules=ModuleGateway(retriever=Retriever()),
    )
)
core.__enter__()


def handle(request):
    if request.url.host != "127.0.0.1":
        raise RuntimeError("Unexpected external request: browser fixtures cannot contact providers")
    response = core.request(
        request.method,
        str(request.url.copy_with(scheme="http", host="testserver", port=None)),
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
        content=request.content,
    )
    return httpx.Response(
        response.status_code, content=response.content, headers={"content-type": "application/json"}
    )


product = create_product_app(
    root, port=18501, settings=settings, services=services, transport=httpx.MockTransport(handle)
)
app = FastAPI()


@app.get("/__test__/ready")
def ready():
    return {"ready": True}


@app.post("/__test__/reset")
def reset():
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE provider_quotas, work_items, consolidation_jobs, "
                "embedding_models, reindex_jobs, capture_jobs, capture_events, memory_edges, "
                "memory_versions, memories CASCADE"
            )
        )
    backend.value = None
    backend.locked = False
    return {"url": product.state.issue_launch()}


app.mount("/", product)

if __name__ == "__main__":
    try:
        uvicorn.run(app, host="127.0.0.1", port=18501, log_level="warning", access_log=False)
    finally:
        core.__exit__(None, None, None)
        engine.dispose()
        folder.cleanup()
