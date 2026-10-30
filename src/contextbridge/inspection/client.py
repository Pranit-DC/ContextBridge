"""HTTP client for the inspection viewer. It speaks only to the service API, never to SQL.

A client is bound to one project. Every ID operation inspects the memory first and treats a memory
from another project as absent, so the selected view cannot read or change other projects' data.
(The service's token itself spans the developer's projects; this boundary is enforced here.)
Errors are one of a few fixed kinds with fixed messages: no response body, input, or credential
is ever copied into an exception.
"""

import ipaddress
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import TypeAdapter, ValidationError

from contextbridge.contracts import (
    BrowseQuery,
    BrowseResult,
    CapturedEvent,
    IngestionResponse,
    JobResponse,
    MemoryRecord,
    RetrievalQuery,
    RetrievalResult,
)
from contextbridge.management import (
    ConsolidationRequest,
    ConsolidationSubmission,
    IndexingState,
    LifecycleResult,
    LifecycleState,
    RestoreMemory,
    RetiredQuery,
    RetiredResult,
    RetireMemory,
    RuntimeState,
)
from contextbridge.schemas import (
    CreateMemory,
    InspectionResponse,
    MemoryResponse,
    Scope,
    SearchMemories,
    UpdateMemory,
)

MESSAGES = {
    "unavailable": "The memory service is unavailable. Try again shortly.",
    "unauthorized": "The memory service rejected the access token. Check the token.",
    "not_found": "That memory was not found in the selected project.",
    "conflict": "The memory changed since it was loaded. Review the latest version first.",
    "invalid": "The request was rejected. Check the values and try again.",
    "unexpected": "The memory service returned an unexpected response.",
}


class ViewerError(Exception):
    """A fixed-message failure; ``kind`` is a key of MESSAGES."""

    def __init__(self, kind: str):
        kind = kind if kind in MESSAGES else "unexpected"
        super().__init__(MESSAGES[kind])
        self.kind = kind
        self.message = MESSAGES[kind]


@dataclass(frozen=True)
class ViewerSettings:
    api_url: str = "http://127.0.0.1:8000"
    token: str = field(default="", repr=False)
    timeout: float = 10.0
    # Remote services are refused unless explicitly allowed, and then only over https.
    allow_remote: bool = False

    def __post_init__(self):
        if not self.token or not self.timeout > 0:
            raise ValueError("Invalid viewer configuration")
        try:
            parts = urlsplit(self.api_url)
            host, _ = parts.hostname, parts.port
        except ValueError:
            raise ValueError("Invalid viewer configuration") from None
        if (
            parts.scheme not in ("http", "https")
            or not host
            or parts.username is not None
            or parts.password is not None
            or parts.path not in ("", "/")
            or parts.query
            or parts.fragment
        ):
            raise ValueError("Invalid viewer configuration")
        if not _is_loopback(host) and not (self.allow_remote and parts.scheme == "https"):
            raise ValueError("Invalid viewer configuration")

    @property
    def origin(self) -> str:
        return self.api_url.rstrip("/")


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class HttpViewerClient:
    def __init__(
        self,
        settings: ViewerSettings,
        project_id: str,
        transport: httpx.BaseTransport | None = None,
    ):
        if not project_id or not project_id.strip():
            raise ValueError("A project is required")
        self.settings = settings
        self.project_id = project_id.strip()
        self.transport = transport

    # -- transport ---------------------------------------------------------------------------

    def _request(self, method: str, path: str, body: Any = None) -> Any:
        try:
            with httpx.Client(
                base_url=self.settings.origin,
                headers={"Authorization": f"Bearer {self.settings.token}"},
                timeout=self.settings.timeout,
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
            ) as client:
                response = client.request(method, path, json=body)
        except httpx.HTTPError:
            raise ViewerError("unavailable") from None
        status = response.status_code
        if status in (401, 403):
            raise ViewerError("unauthorized")
        if status == 404:
            raise ViewerError("not_found")
        if status == 409:
            raise ViewerError("conflict")
        if status == 422:
            raise ViewerError("invalid")
        if status >= 500:
            raise ViewerError("unavailable")
        if not response.is_success:
            raise ViewerError("unexpected")
        if status == 204:
            return None
        try:
            return response.json()
        except ValueError:
            raise ViewerError("unexpected") from None

    @staticmethod
    def _parse(model, body):
        try:
            return TypeAdapter(model).validate_python(body)
        except ValidationError:
            raise ViewerError("unexpected") from None

    @staticmethod
    def _memory_id(memory_id) -> UUID:
        try:
            return UUID(str(memory_id))
        except ValueError:
            raise ViewerError("invalid") from None

    @staticmethod
    def _validate(model, payload):
        try:
            return model.model_validate(payload)
        except (ValidationError, TypeError, ValueError):
            raise ViewerError("invalid") from None

    # -- scope boundary ----------------------------------------------------------------------

    def _in_selected_project(self, memory: MemoryResponse) -> bool:
        return memory.scope == Scope.DEVELOPER or memory.project_id == self.project_id

    def _guard(self, memory: MemoryResponse) -> None:
        if not self._in_selected_project(memory):
            # Indistinguishable from a missing ID, so other projects' IDs are not confirmed.
            raise ViewerError("not_found")

    def _require_selected_project(self, scope: Scope, project_id: str | None) -> None:
        if scope == Scope.PROJECT and project_id != self.project_id:
            raise ViewerError("invalid")

    # -- operations --------------------------------------------------------------------------

    def status(self) -> dict:
        data = self._request("GET", "/health/ready")
        if data != {"status": "ready"}:
            raise ViewerError("unexpected")
        return {"status": "ready", "project_id": self.project_id}

    def search(self, query: dict) -> dict:
        request = self._validate(SearchMemories, query)
        self._require_selected_project(request.scope, request.project_id)
        data = self._request("POST", "/v1/memories/search", request.model_dump(mode="json"))
        memories = self._parse(list[MemoryResponse], data)
        for memory in memories:
            allowed_developer = request.scope == Scope.DEVELOPER or request.include_developer
            if (memory.scope == Scope.DEVELOPER and not allowed_developer) or (
                not self._in_selected_project(memory)
            ):
                raise ViewerError("unexpected")
        return {"memories": [m.model_dump(mode="json") for m in memories[: request.limit]]}

    def browse(self, query: dict) -> dict:
        request = self._validate(BrowseQuery, query)
        self._require_selected_project(request.scope, request.project_id)
        data = self._request("POST", "/v1/inspection/browse", request.model_dump(mode="json"))
        result = self._parse(BrowseResult, data)
        for item in result.items:
            if item.memory.scope != request.scope or not self._in_selected_project(item.memory):
                raise ViewerError("unexpected")
        return result.model_dump(mode="json")

    def inspect(self, memory_id) -> dict:
        return self._inspection(self._memory_id(memory_id)).model_dump(mode="json")

    def _inspection(self, memory_id: UUID) -> InspectionResponse:
        data = self._request("GET", f"/v1/memories/{memory_id}")
        result = self._parse(InspectionResponse, data)
        if result.memory.id != memory_id:
            raise ViewerError("unexpected")
        self._guard(result.memory)
        return result

    def capabilities(self) -> dict:
        data = self._request("GET", "/v1/status")
        return self._parse(RuntimeState, data).model_dump(mode="json")

    def retrieve(self, query: dict) -> dict:
        request = self._validate(RetrievalQuery, {"schema_version": 1, **query})
        self._require_selected_project(request.scope, request.project_id)
        result = self._parse(
            RetrievalResult,
            self._request("POST", "/v1/retrieval/search", request.model_dump(mode="json")),
        )
        for card in result.cards:
            if (card.scope == Scope.PROJECT and card.project_id != self.project_id) or (
                card.scope == Scope.DEVELOPER
                and not request.include_developer
                and request.scope != Scope.DEVELOPER
            ):
                raise ViewerError("unexpected")
        if len(result.cards) > request.limit:
            raise ViewerError("unexpected")
        return result.model_dump(mode="json")

    def save(self, payload: dict) -> dict:
        request = self._validate(CreateMemory, payload)
        self._require_selected_project(request.scope, request.project_id)
        result = self._parse(
            MemoryResponse, self._request("POST", "/v1/memories", request.model_dump(mode="json"))
        )
        self._guard(result)
        if (result.scope, result.project_id) != (request.scope, request.project_id):
            raise ViewerError("unexpected")
        if (result.type, result.conditions, result.version.content, result.version.source) != (
            request.type,
            request.conditions,
            request.content,
            request.source,
        ):
            raise ViewerError("unexpected")
        return result.model_dump(mode="json")

    def _capture_binding(self):
        if self.capabilities()["capture_project_id"] != self.project_id:
            raise ViewerError("invalid")

    def import_conversation(self, payload: dict) -> dict:
        from contextbridge.engine.errors import ModuleError
        from contextbridge.formation.transcript import import_transcript

        self._capture_binding()
        event = self._validate(CapturedEvent, payload)
        if event.scope != Scope.PROJECT or event.project_id != self.project_id:
            raise ViewerError("invalid")
        if event.capture_method != "manual_import":
            raise ViewerError("invalid")
        try:
            normalized = import_transcript(
                **event.model_dump(exclude={"schema_version", "capture_method"})
            )
        except ModuleError:
            raise ViewerError("invalid") from None
        result = self._parse(
            IngestionResponse, self._request("POST", "/v1/interactions", normalized)
        )
        if result.event_id != event.event_id:
            raise ViewerError("unexpected")
        return result.model_dump(mode="json")

    def import_bundle(self, payload: dict) -> dict:
        from contextbridge.evidence_time.contracts import EvidenceBundle

        self._capture_binding()
        bundle = self._validate(EvidenceBundle, payload)
        for event in bundle.events:
            if event.scope != Scope.PROJECT or event.project_id != self.project_id:
                raise ViewerError("invalid")
        result = self._parse(
            IngestionResponse,
            self._request("POST", "/v2/interactions/bundles", bundle.model_dump(mode="json")),
        )
        if result.event_id != bundle.bundle_id:
            raise ViewerError("unexpected")
        return result.model_dump(mode="json")

    def provenance(self, memory_id) -> dict:
        from contextbridge.evidence_time.contracts import ProvenanceResult

        memory = self._inspection(self._memory_id(memory_id)).memory
        payload = {
            "scope": memory.scope.value,
            "project_id": memory.project_id,
            "memory_id": str(memory.id),
            "version": memory.current_version,
        }
        result = self._parse(
            ProvenanceResult, self._request("POST", "/v2/inspection/provenance", payload)
        )
        if (
            result.memory_id != memory.id
            or result.version != memory.current_version
            or (result.scope, result.project_id) != (memory.scope, memory.project_id)
        ):
            raise ViewerError("unexpected")
        return result.model_dump(mode="json")

    def processing(self, job_id) -> dict:
        self._capture_binding()
        identifier = self._memory_id(job_id)
        result = self._parse(JobResponse, self._request("GET", f"/v1/jobs/{identifier}"))
        if result.job_id != identifier:
            raise ViewerError("unexpected")
        # Guard returned IDs before displaying or selecting them.
        for memory_id in result.memory_ids:
            self._inspection(memory_id)
        return result.model_dump(mode="json")

    def recent_processing(self):
        from urllib.parse import urlencode

        self._capture_binding()
        result = self._parse(
            list[JobResponse],
            self._request("GET", "/v1/jobs?" + urlencode({"project_id": self.project_id})),
        )
        if len(result) > 20:
            raise ViewerError("unexpected")
        for job in result:
            for memory_id in job.memory_ids:
                self._inspection(memory_id)
        return [job.model_dump(mode="json") for job in result]

    def retired(self, query: dict) -> dict:
        request = self._validate(RetiredQuery, query)
        self._require_selected_project(request.scope, request.project_id)
        result = self._parse(
            RetiredResult,
            self._request("POST", "/v1/inspection/retired", request.model_dump(mode="json")),
        )
        for item in result.items:
            self._guard(item.memory)
            if item.memory.scope != request.scope:
                raise ViewerError("unexpected")
        return result.model_dump(mode="json")

    def lifecycle(self, memory_id) -> dict:
        identifier = self._memory_id(memory_id)
        self._inspection(identifier)
        return self._parse(
            LifecycleState, self._request("GET", f"/v1/memories/{identifier}/lifecycle")
        ).model_dump(mode="json")

    def indexing(self, memory_id) -> dict:
        identifier = self._memory_id(memory_id)
        self._inspection(identifier)
        return self._parse(
            IndexingState, self._request("GET", f"/v1/memories/{identifier}/indexing")
        ).model_dump(mode="json")

    def sources(self, memory_id) -> list[dict]:
        identifier = self._memory_id(memory_id)
        original = self._inspection(identifier).memory
        rows = self._parse(
            list[MemoryRecord], self._request("GET", f"/v1/memories/{identifier}/sources")
        )
        if len(rows) > 200:
            raise ViewerError("unexpected")
        for row in rows:
            if (row.memory.scope, row.memory.project_id) != (original.scope, original.project_id):
                raise ViewerError("unexpected")
            self._guard(row.memory)
        return [row.model_dump(mode="json") for row in rows]

    def change_lifecycle(self, memory_id, action: str, payload: dict) -> dict:
        if action not in ("retire", "restore"):
            raise ViewerError("invalid")
        identifier = self._memory_id(memory_id)
        memory = self._inspection(identifier).memory
        request = self._validate(RetireMemory if action == "retire" else RestoreMemory, payload)
        if (request.scope, request.project_id) != (memory.scope, memory.project_id):
            raise ViewerError("invalid")
        result = self._parse(
            LifecycleResult,
            self._request(
                "POST", f"/v1/memories/{identifier}/{action}", request.model_dump(mode="json")
            ),
        )
        self._guard(result.memory)
        if result.memory.id != identifier:
            raise ViewerError("unexpected")
        return result.model_dump(mode="json")

    def consolidate(self, payload: dict) -> dict:
        self._capture_binding()
        request = self._validate(ConsolidationRequest, payload)
        if request.scope != Scope.PROJECT or request.project_id != self.project_id:
            raise ViewerError("invalid")
        result = self._parse(
            ConsolidationSubmission,
            self._request("POST", "/v1/consolidations", request.model_dump(mode="json")),
        )
        return result.model_dump(mode="json")

    def consolidation_status(self, job_id) -> dict:
        self._capture_binding()
        identifier = self._memory_id(job_id)
        data = self._request("GET", f"/v1/consolidations/{identifier}")
        if not isinstance(data, dict) or data.get("status") not in (
            "queued",
            "running",
            "succeeded",
            "failed",
            "deferred",
            "cancelled",
        ):
            raise ViewerError("unexpected")
        if data.get("job_id") != str(identifier):
            raise ViewerError("unexpected")
        from contextbridge.contracts.messages import ReasonCode

        codes = self._parse(list[ReasonCode], data.get("reason_codes"))
        ids = self._parse(list[UUID], data.get("memory_ids"))
        if len(codes) > 20 or len(ids) > 200:
            raise ViewerError("unexpected")
        for memory_id in ids:
            self._inspection(memory_id)
        return {
            "status": data["status"],
            "reason_codes": codes,
            "memory_ids": [str(i) for i in ids],
        }

    def correct(self, memory_id, update: dict) -> dict:
        """Send an explicit correction naming the version it was based on (``expected_version``).

        A stale version raises ``ViewerError("conflict")``; the caller reloads and asks the user,
        and nothing here ever retries against a newer version.
        """
        identifier = self._memory_id(memory_id)
        body = self._validate(UpdateMemory, update).model_dump(mode="json")
        self._inspection(identifier)
        data = self._request("PUT", f"/v1/memories/{identifier}", body)
        result = self._parse(MemoryResponse, data)
        self._guard(result)
        return result.model_dump(mode="json")

    def forget(self, memory_id) -> None:
        """Permanently delete. The caller must have obtained the user's confirmation."""
        identifier = self._memory_id(memory_id)
        self._inspection(identifier)
        self._request("DELETE", f"/v1/memories/{identifier}")
