"""Exercise the memory lifecycle through two independent HTTP clients."""

import argparse
from uuid import uuid4

import httpx

from contextbridge.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    settings = Settings()
    headers = {"Authorization": f"Bearer {settings.api_token.get_secret_value()}"}
    memory_id = None
    with (
        httpx.Client(base_url=args.url, headers=headers) as agent_a,
        httpx.Client(base_url=args.url, headers=headers) as agent_b,
    ):
        try:
            response = agent_a.post(
                "/v1/memories",
                json={
                    "request_id": str(uuid4()),
                    "scope": "project",
                    "project_id": "demo-contextbridge",
                    "type": "DECISION",
                    "content": "Use PostgreSQL for V1.",
                    "source": {
                        "kind": "user",
                        "agent": "codex",
                        "session": "demo-session-a",
                        "interaction": "turn-1",
                        "evidence": "We decided to use PostgreSQL for V1.",
                    },
                },
            )
            response.raise_for_status()
            memory_id = response.json()["id"]
            query = {"scope": "project", "project_id": "demo-contextbridge", "query": "PostgreSQL"}
            results = agent_b.post("/v1/memories/search", json=query)
            results.raise_for_status()
            assert any(m["id"] == memory_id for m in results.json())
            print("PASS: an independent client retrieved the stored decision")
            path = f"/v1/memories/{memory_id}"
            updated = agent_b.put(
                path,
                json={
                    "expected_version": 1,
                    "content": "Use SQLite for V1.",
                    "source": {
                        "kind": "user",
                        "agent": "claude-code",
                        "session": "demo-session-b",
                        "interaction": "turn-2",
                        "evidence": "We changed the V1 database to SQLite.",
                    },
                },
            )
            updated.raise_for_status()
            query["query"] = "SQLite"
            current = agent_a.post("/v1/memories/search", json=query)
            current.raise_for_status()
            assert any(m["id"] == memory_id for m in current.json())
            inspection = agent_a.get(path)
            inspection.raise_for_status()
            assert [v["status"] for v in inspection.json()["history"]] == ["SUPERSEDED", "ACTIVE"]
            print("PASS: changed decision is current and its prior version remains inspectable")
        finally:
            if memory_id is not None:
                forgotten = agent_a.delete(f"/v1/memories/{memory_id}")
                forgotten.raise_for_status()
                print("PASS: demo memory and evidence removed")


if __name__ == "__main__":
    main()
