"""Screen logic for the viewer: every outcome becomes a result with a plain-language notice.

The controller never raises to the UI and never logs. It uses only the injected client (HTTP to the
service), so a fake client can drive every state in tests. Rules it enforces:

- Search needs a real query; an empty query is not a way to list everything. Browsing has its own,
  paginated call.
- A correction names the version the user was looking at. If the service says it is stale, the
  latest version is reloaded, the user's draft is kept, and nothing is retried.
- Deleting needs an explicit confirmation, or no request is sent.
"""

from dataclasses import dataclass, field, replace
from uuid import uuid4

from contextbridge.inspection.client import ViewerError
from contextbridge.inspection.viewmodel import (
    DetailView,
    MemoryRow,
    Notice,
    detail_from,
    plain,
    rows_from_browse,
    rows_from_cards,
    rows_from_memories,
)

MAX_TEXT = 8000
UNAVAILABLE = Notice("error", "Something went wrong while talking to the memory service.")


def notice_for(error: Exception) -> Notice:
    if isinstance(error, ViewerError):
        level = "warning" if error.kind in ("conflict", "not_found") else "error"
        return Notice(level, error.message)
    return UNAVAILABLE


@dataclass(frozen=True)
class ListResult:
    rows: list[MemoryRow] = field(default_factory=list)
    notice: Notice | None = None
    next_cursor: str | None = None


@dataclass(frozen=True)
class DetailResult:
    detail: DetailView | None = None
    notice: Notice | None = None


@dataclass(frozen=True)
class CorrectionResult:
    ok: bool
    detail: DetailView | None = None
    notice: Notice | None = None
    conflict: bool = False
    # What the user typed, returned so a failed attempt never loses their text.
    draft_content: str = ""
    draft_evidence: str = ""


@dataclass(frozen=True)
class ForgetResult:
    ok: bool
    notice: Notice


@dataclass(frozen=True)
class StatusResult:
    ready: bool
    notice: Notice


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    data: dict | list[dict] = field(default_factory=dict)
    notice: Notice | None = None


class ViewerController:
    def __init__(self, client, *, agent: str = "contextbridge-viewer", session: str | None = None):
        self.client = client
        self.agent = agent
        self.session = session or f"viewer-{uuid4().hex[:12]}"

    def action(self, method: str, *args) -> ActionResult:
        try:
            return ActionResult(True, getattr(self.client, method)(*args))
        except Exception as error:
            return ActionResult(False, notice=notice_for(error))

    def retrieve(
        self, text: str, *, conditions=None, include_developer=False, more=False, as_of=None
    ) -> ListResult:
        text = (text or "").strip()
        if not text:
            return ListResult(notice=Notice("info", "Type something to search for."))
        result = self.action(
            "retrieve",
            {
                "scope": "project",
                "project_id": self.client.project_id,
                "query": text,
                "conditions": conditions or {},
                "include_developer": include_developer,
                "as_of": as_of,
                "limit": 5 if more else 3,
            },
        )
        if not result.ok:
            return ListResult(notice=result.notice)
        try:
            rows = rows_from_cards(result.data["cards"])
        except Exception as error:
            return ListResult(notice=notice_for(error))
        warning = None
        if result.data["degraded"]:
            warning = Notice(
                "warning",
                "Search is using a reduced service. "
                "Meaning search or evidence checking is unavailable; check details. "
                + ", ".join(plain(w) for w in result.data["warnings"]),
            )
        elif not rows:
            warning = Notice("info", "No memories matched these filters.")
        return ListResult(rows=rows, notice=warning)

    def retired(self, cursor=None) -> ListResult:
        result = self.action(
            "retired",
            {
                "scope": "project",
                "project_id": self.client.project_id,
                "limit": 20,
                "cursor": cursor,
            },
        )
        if not result.ok:
            return ListResult(notice=result.notice)
        rows = [
            replace(r, status_label="Retired")
            for r in rows_from_memories([item["memory"] for item in result.data["items"]])
        ]
        return ListResult(
            rows=rows,
            next_cursor=result.data.get("next_cursor"),
            notice=None if rows else Notice("info", "No retired memories here."),
        )

    def source(self, interaction, evidence):
        return {
            "kind": "user",
            "agent": self.agent,
            "session": self.session,
            "interaction": interaction,
            "evidence": evidence,
        }

    def save(self, request_id, content, evidence, type_, conditions=None, valid_from=None):
        return self.action(
            "save",
            {
                "request_id": request_id,
                "scope": "project",
                "project_id": self.client.project_id,
                "type": type_,
                "content": content,
                "source": self.source(f"viewer-save-{request_id}", evidence),
                "conditions": conditions or {},
                "valid_from": valid_from,
            },
        )

    def import_conversation(self, event_id, occurred_at, messages_json):
        import json

        from contextbridge.capture_adapters.transcript import MAX_FILE_BYTES, unique_fields

        if len(messages_json.encode("utf-8")) > MAX_FILE_BYTES:
            return ActionResult(False, notice=Notice("warning", "The conversation is too large."))
        try:
            messages = json.loads(messages_json, object_pairs_hook=unique_fields)
        except (ValueError, RecursionError):
            return ActionResult(
                False,
                notice=Notice(
                    "warning",
                    "Enter a valid message list with explicit user, assistant or tool roles.",
                ),
            )
        return self.action(
            "import_conversation",
            {
                "schema_version": 1,
                "event_id": event_id,
                "scope": "project",
                "project_id": self.client.project_id,
                "agent": self.agent,
                "session": self.session,
                "interaction": f"viewer-import-{event_id}",
                "occurred_at": occurred_at,
                "capture_method": "manual_import",
                "messages": messages,
            },
        )

    def change_lifecycle(
        self, memory_id, action, expected_version, *, source_version=None, evidence=""
    ):
        inspected = self.action("inspect", memory_id)
        if not inspected.ok:
            return inspected
        memory = inspected.data["memory"]
        body = {
            "scope": memory["scope"],
            "project_id": memory["project_id"],
            "expected_version": expected_version,
        }
        if action == "restore":
            body.update(
                source_version=source_version,
                source=self.source(f"viewer-restore-{uuid4().hex}", evidence),
            )
        return self.action("change_lifecycle", memory_id, action, body)

    # -- reading -----------------------------------------------------------------------------

    def status(self) -> StatusResult:
        try:
            self.client.status()
        except Exception as error:
            return StatusResult(False, notice_for(error))
        return StatusResult(True, Notice("success", "Connected to the memory service."))

    def search(
        self,
        text: str,
        *,
        conditions: dict | None = None,
        include_developer: bool = False,
        limit: int = 10,
        as_of=None,
    ) -> ListResult:
        text = (text or "").strip()
        if not text:
            return ListResult(notice=Notice("info", "Type something to search for."))
        query = {
            "scope": "project",
            "project_id": self.client.project_id,
            "query": text,
            "include_developer": include_developer,
            "conditions": conditions or {},
            "as_of": as_of,
            "limit": limit,
        }
        try:
            rows = rows_from_memories(self.client.search(query)["memories"])
        except Exception as error:
            return ListResult(notice=notice_for(error))
        if not rows:
            return ListResult(
                notice=Notice(
                    "info",
                    "Nothing matched. Search looks for the words you typed; "
                    "it does not guess related meanings.",
                )
            )
        return ListResult(rows=rows)

    def browse(
        self,
        *,
        cursor: str | None = None,
        scope: str = "project",
        conditions: dict | None = None,
        as_of=None,
        limit: int = 20,
    ) -> ListResult:
        query = {
            "schema_version": 1,
            "scope": scope,
            "project_id": self.client.project_id if scope == "project" else None,
            "conditions": conditions or {},
            "as_of": as_of,
            "limit": limit,
            "cursor": cursor,
        }
        try:
            result = self.client.browse(query)
            rows = rows_from_browse(result["items"])
        except Exception as error:
            return ListResult(notice=notice_for(error))
        if not rows and cursor is None:
            return ListResult(notice=Notice("info", "Nothing is saved here yet."))
        return ListResult(rows=rows, next_cursor=result.get("next_cursor"))

    def open(self, memory_id: str) -> DetailResult:
        try:
            return DetailResult(detail=detail_from(self.client.inspect(memory_id)))
        except Exception as error:
            return DetailResult(notice=notice_for(error))

    # -- changing ----------------------------------------------------------------------------

    def correct(
        self, memory_id: str, expected_version: int, content: str, evidence: str
    ) -> CorrectionResult:
        content, evidence = (content or "").strip(), (evidence or "").strip()
        draft = {"draft_content": content, "draft_evidence": evidence}
        if not content or not evidence:
            return CorrectionResult(
                False,
                notice=Notice("warning", "Enter the corrected text and where it comes from."),
                **draft,
            )
        if len(content) > MAX_TEXT or len(evidence) > MAX_TEXT:
            return CorrectionResult(
                False, notice=Notice("warning", "That text is too long to save."), **draft
            )
        update = {
            "expected_version": expected_version,
            "content": content,
            "source": {
                "kind": "user",
                "agent": self.agent,
                "session": self.session,
                "interaction": f"viewer-correction-{uuid4().hex[:12]}",
                "evidence": evidence,
            },
        }
        try:
            saved = self.client.correct(memory_id, update)
        except ViewerError as error:
            if error.kind == "conflict":
                return self._after_conflict(memory_id, draft)
            return CorrectionResult(False, notice=notice_for(error), **draft)
        except Exception as error:
            return CorrectionResult(False, notice=notice_for(error), **draft)
        reloaded = self.open(memory_id)
        number = saved.get("current_version")
        return CorrectionResult(
            True,
            detail=reloaded.detail,
            notice=Notice("success", f"Saved as version {number}. The earlier version is kept."),
        )

    def _after_conflict(self, memory_id: str, draft: dict) -> CorrectionResult:
        """Show the newer version and keep the draft; the user decides whether to try again."""
        latest = self.open(memory_id)
        return CorrectionResult(
            False,
            detail=latest.detail,
            conflict=True,
            notice=Notice(
                "warning",
                "This memory was changed after you opened it, so your correction was not saved. "
                "Review the latest version below, then submit again if it is still right.",
            ),
            **draft,
        )

    def forget(self, memory_id: str, confirmed: bool) -> ForgetResult:
        if confirmed is not True:
            return ForgetResult(
                False, Notice("warning", "Confirm that you want to delete this memory permanently.")
            )
        try:
            self.client.forget(memory_id)
        except Exception as error:
            return ForgetResult(False, notice_for(error))
        return ForgetResult(
            True,
            Notice("success", "Deleted permanently, with its history and evidence."),
        )
