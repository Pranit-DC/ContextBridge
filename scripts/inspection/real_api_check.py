"""Exercise the viewer's client and controller against a RUNNING ContextBridge service.

This is a real-component check (real HTTP, real PostgreSQL behind the service), not a unit test.
It creates its own memories under throwaway project IDs and removes them afterwards, but it does
write to whatever database the service uses, so point it at a disposable local service.

    uv run python scripts/inspection/real_api_check.py --env-file .env

Only the API token is read from the env file. The token and memory content are never printed.
"""

import argparse
import sys
from pathlib import Path
from uuid import uuid4

import httpx

from contextbridge.inspection.client import HttpViewerClient, ViewerError, ViewerSettings
from contextbridge.inspection.controller import ViewerController

results: list[tuple[str, bool]] = []


def check(name: str, condition: bool) -> None:
    results.append((name, bool(condition)))
    print(f"{'PASS' if condition else 'FAIL'}  {name}")


def read_token(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CONTEXTBRIDGE_API_TOKEN="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("CONTEXTBRIDGE_API_TOKEN not found in the env file")


def source(text: str) -> dict:
    return {
        "kind": "user",
        "agent": "real-api-check",
        "session": "real-api-check",
        "interaction": f"check-{uuid4().hex[:8]}",
        "evidence": text,
    }


class Seeder:
    """Creates and cleans up memories directly through the API, independent of the viewer."""

    def __init__(self, url: str, token: str):
        self.http = httpx.Client(
            base_url=url, headers={"Authorization": f"Bearer {token}"}, trust_env=False, timeout=15
        )
        self.created: list[str] = []

    def create(self, project: str, content: str, **extra) -> dict:
        body = {
            "request_id": str(uuid4()),
            "scope": "project",
            "project_id": project,
            "type": "DECISION",
            "content": content,
            "source": source(f"Stated for the check: {content}"),
            **extra,
        }
        response = self.http.post("/v1/memories", json=body)
        response.raise_for_status()
        self.created.append(response.json()["id"])
        return response.json()

    def exists(self, memory_id: str) -> bool:
        return self.http.get(f"/v1/memories/{memory_id}").status_code == 200

    def cleanup(self) -> None:
        for memory_id in self.created:
            self.http.delete(f"/v1/memories/{memory_id}")
        self.http.close()


def run(url: str, token: str) -> None:
    mine, other = f"viewer-check-{uuid4().hex[:8]}", f"viewer-check-{uuid4().hex[:8]}"
    settings = ViewerSettings(url, token)
    seed = Seeder(url, token)
    try:
        client = HttpViewerClient(settings, mine)
        controller = ViewerController(client, session="real-api-check")

        check("status reports ready", controller.status().ready)
        bad = ViewerController(HttpViewerClient(ViewerSettings(url, "x" * 40), mine))
        check("a wrong token is reported as a token problem", "token" in bad.status().notice.text)

        # Browse: empty, then populated and paginated.
        check(
            "an empty project says nothing is saved",
            "Nothing is saved" in controller.browse().notice.text,
        )
        first = seed.create(mine, "The viewer check uses PostgreSQL for storage.")
        seed.create(mine, "The viewer check prefers explicit evidence.")
        seed.create(mine, "The viewer check keeps old versions.")
        foreign = seed.create(other, "A memory that belongs to a different project.")
        page1 = controller.browse(limit=2)
        page2 = controller.browse(limit=2, cursor=page1.next_cursor)
        total = len(page1.rows) + len(page2.rows)
        check(
            "browse pages through all of this project's memories", total == 3 and page1.next_cursor
        )
        ids = {r.memory_id for r in page1.rows + page2.rows}
        check("browse never includes another project's memory", foreign["id"] not in ids)
        check("browse pages do not overlap", len(ids) == 3)

        # Search.
        found = controller.search("PostgreSQL")
        check(
            "search finds a memory by its words", [r.memory_id for r in found.rows] == [first["id"]]
        )
        check(
            "search does not leak the other project",
            not controller.search("different project").rows,
        )
        check(
            "an empty search sends nothing and explains",
            controller.search("  ").notice.level == "info",
        )

        # Inspect and the project boundary.
        detail = controller.open(first["id"]).detail
        check(
            "details show the evidence",
            detail and "Stated for the check" in detail.current.evidence,
        )
        check("another project's id is not found", controller.open(foreign["id"]).detail is None)

        # Correction against the opened version, then a stale one.
        done = controller.correct(
            first["id"], 1, "The viewer check uses SQLite.", "Changed in the check"
        )
        check("a correction saves a new version", done.ok and done.detail.expected_version == 2)
        check("the earlier version is kept", [v.number for v in done.detail.history] == [2, 1])
        check(
            "the relationship is described",
            "Version 2 replaced version 1." in done.detail.relationships,
        )
        stale = controller.correct(first["id"], 1, "A stale edit", "Based on version 1")
        check("a stale correction conflicts", stale.conflict and not stale.ok)
        check(
            "the stale attempt shows the newer version",
            stale.detail.current.content.endswith("SQLite."),
        )
        check("the stale attempt keeps the draft", stale.draft_content == "A stale edit")
        check(
            "the stale attempt saved nothing",
            controller.open(first["id"]).detail.expected_version == 2,
        )

        # Another project's memory cannot be changed through this view.
        check(
            "correcting another project is refused",
            not controller.correct(foreign["id"], 1, "x", "y").ok,
        )
        check(
            "forgetting another project is refused", not controller.forget(foreign["id"], True).ok
        )
        check("the other project's memory is untouched", seed.exists(foreign["id"]))

        # Deletion needs confirmation.
        check(
            "forget without confirmation does nothing", not controller.forget(first["id"], False).ok
        )
        check("the memory still exists after an unconfirmed forget", seed.exists(first["id"]))
        gone = controller.forget(first["id"], True)
        check("a confirmed forget deletes", gone.ok and not seed.exists(first["id"]))
        check("a forgotten memory no longer opens", controller.open(first["id"]).detail is None)
        check("a bad id is handled", controller.open("not-a-uuid").detail is None)

        # Failure handling with a stopped/wrong service.
        down = ViewerController(HttpViewerClient(ViewerSettings("http://127.0.0.1:9", token), mine))
        check(
            "an unreachable service reads as unavailable",
            "unavailable" in down.status().notice.text,
        )
        try:
            client.inspect(str(uuid4()))
        except ViewerError as error:
            check("an unknown memory is not found", error.kind == "not_found")
    finally:
        seed.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    run(args.url, read_token(args.env_file))
    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
