from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

from contextbridge.context_models import ContextQuery, ContextResult
from contextbridge.contracts import RetrievalQuery, RetrievalResult
from contextbridge.management import LifecycleResult, RestoreMemory, RetireMemory
from contextbridge.mcp_adapter.arguments import (
    ContextArguments,
    Evidence,
    FollowupArguments,
    MemoryReference,
    NoArguments,
    ProvenanceArguments,
    RestoreArguments,
    RetireArguments,
    SearchArguments,
    TemporalArguments,
    UpdateArguments,
    WriteArguments,
)
from contextbridge.mcp_adapter.config import MCPSettings
from contextbridge.schemas import (
    CreateMemory,
    InspectionResponse,
    MemoryResponse,
    Scope,
    SearchMemories,
    Source,
    UpdateMemory,
)


class GatewayError(Exception):
    """Only fixed, safe messages may cross the MCP boundary."""


class MemoryGateway:
    def __init__(self, settings: MCPSettings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    @asynccontextmanager
    async def client(self):
        async with httpx.AsyncClient(
            base_url=str(self.settings.api_url),
            headers={"Authorization": f"Bearer {self.settings.api_token.get_secret_value()}"},
            timeout=self.settings.request_timeout,
            follow_redirects=False,
            trust_env=False,
            transport=self.transport,
        ) as client:
            yield client

    async def request(self, client: httpx.AsyncClient, method: str, path: str, body=None):
        try:
            response = await client.request(method, path, json=body)
        except httpx.HTTPError:
            raise GatewayError(
                "Memory service unavailable; the operation may have completed. "
                "Inspect before retrying an update or forget. Reuse the same request_id and "
                "source for a create retry; never retry a create after forgetting it."
            ) from None
        if response.status_code in (401, 403):
            raise GatewayError("Memory service authentication failed. Check adapter credentials.")
        if response.status_code == 404:
            raise GatewayError("Memory not found in the configured scope.")
        if response.status_code == 409:
            raise GatewayError(
                "Memory conflict. Inspect the current version before updating; "
                "a create request_id must retain its original payload."
            )
        if response.status_code == 422:
            raise GatewayError(
                "Memory request rejected. Check evidence, timestamps, and credential-free content."
            )
        if not response.is_success:
            raise GatewayError("Memory service unavailable or returned an unexpected status.")
        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError:
            raise GatewayError("Memory service returned an invalid response.") from None

    @staticmethod
    def parse(model, body):
        try:
            return TypeAdapter(model).validate_python(body)
        except ValidationError:
            raise GatewayError("Memory service returned an invalid response.") from None

    def project_for(self, scope: Scope) -> str | None:
        return self.settings.project_id if scope == Scope.PROJECT else None

    def source(self, evidence: Evidence) -> Source:
        return Source(
            **evidence.model_dump(), agent=self.settings.agent_id, session=self.settings.session_id
        )

    def guard(self, memory: MemoryResponse):
        if memory.scope == Scope.PROJECT and memory.project_id != self.settings.project_id:
            # Do not disclose whether a caller-supplied ID belongs to another project.
            raise GatewayError("Memory not found in the configured scope.")

    @staticmethod
    def card(memory: MemoryResponse) -> dict[str, Any]:
        card = memory.model_dump(mode="json")
        version = card["version"]
        version["content_truncated"] = len(version["content"]) > 1500
        version["content"] = version["content"][:1500]
        # Retrieval provides references; explicit inspection provides full evidence/history.
        version["source"].pop("evidence")
        return card

    async def search(self, args: SearchArguments):
        body = SearchMemories(
            **args.model_dump(), project_id=self.project_for(args.scope)
        ).model_dump(mode="json")
        async with self.client() as client:
            data = await self.request(client, "POST", "/v1/memories/search", body)
        memories = self.parse(list[MemoryResponse], data)
        for memory in memories:
            self.guard(memory)
            if memory.scope != args.scope and not (
                args.scope == Scope.PROJECT
                and args.include_developer
                and memory.scope == Scope.DEVELOPER
            ):
                raise GatewayError("Memory service returned a result outside the requested scope.")
        return {
            "memories": [self.card(memory) for memory in memories[: args.limit]],
            "retrieval": "lexical",
            "project_id": self.settings.project_id,
        }

    async def provenance(self, args: ProvenanceArguments):
        from contextbridge.evidence_time.contracts import ProvenanceQuery, ProvenanceResult

        query = ProvenanceQuery(**args.model_dump(), project_id=self.project_for(args.scope))
        async with self.client() as client:
            data = await self.request(
                client, "POST", "/v2/inspection/provenance", query.model_dump(mode="json")
            )
        result = self.parse(ProvenanceResult, data)
        if (
            result.memory_id != args.memory_id
            or (args.version is not None and result.version != args.version)
            or (result.scope, result.project_id) != (query.scope, query.project_id)
        ):
            raise GatewayError("Memory service returned an invalid response.")
        return result.model_dump(mode="json")

    async def temporal_context(self, args: TemporalArguments):
        from contextbridge.evidence_time.contracts import (
            TemporalContextQuery,
            TemporalContextResult,
        )

        query = TemporalContextQuery(**args.model_dump(), project_id=self.project_for(args.scope))
        async with self.client() as client:
            data = await self.request(
                client, "POST", "/v2/retrieval/temporal-context", query.model_dump(mode="json")
            )
        result = self.parse(TemporalContextResult, data)
        if result.as_of != query.as_of or len(result.items) > args.limit:
            raise GatewayError("Memory service returned an invalid response.")
        seen = set()
        for item in result.items:
            self.guard(item.memory)
            version = item.memory.version
            if (
                item.memory.scope != args.scope
                or item.memory.id != args.memory_id
                or any(args.conditions.get(k) != v for k, v in item.memory.conditions.items())
                or item.memory.current_version != args.expected_version
                or version.id in seen
            ):
                raise GatewayError("Memory service returned an invalid response.")
            seen.add(version.id)
        return result.model_dump(mode="json")

    async def write(self, args: WriteArguments):
        body = CreateMemory(
            **args.model_dump(exclude={"source"}),
            project_id=self.project_for(args.scope),
            source=self.source(args.source),
        ).model_dump(mode="json")
        async with self.client() as client:
            data = await self.request(client, "POST", "/v1/memories", body)
        memory = self.parse(MemoryResponse, data)
        self.guard(memory)
        return memory.model_dump(mode="json")

    async def retrieve(self, args: SearchArguments):
        query = RetrievalQuery(
            schema_version=1, **args.model_dump(), project_id=self.project_for(args.scope)
        )
        async with self.client() as client:
            data = await self.request(
                client, "POST", "/v1/retrieval/search", query.model_dump(mode="json")
            )
        return self.retrieval_result(data, args)

    async def followup(self, args: FollowupArguments):
        query = RetrievalQuery(
            schema_version=1,
            **args.model_dump(exclude={"memory_id", "expected_version"}),
            project_id=self.project_for(args.scope),
        )
        async with self.client() as client:
            data = await self.request(
                client,
                "POST",
                "/v1/retrieval/referenced-search",
                {
                    "memory_id": str(args.memory_id),
                    "expected_version": args.expected_version,
                    "query": query.model_dump(mode="json"),
                },
            )
        return self.retrieval_result(data, args)

    def retrieval_result(self, data, args):
        result = self.parse(RetrievalResult, data)
        if len(result.cards) > args.limit:
            raise GatewayError("Memory service returned an invalid response.")
        for card in result.cards:
            if (
                card.scope == Scope.PROJECT
                and card.project_id != self.settings.project_id
                or card.scope != args.scope
                and not (
                    args.scope == Scope.PROJECT
                    and args.include_developer
                    and card.scope == Scope.DEVELOPER
                )
            ):
                raise GatewayError("Memory service returned a result outside the requested scope.")
        # Preserve V1 warnings/verification and exact bounded content; inspect for evidence.
        return result.model_dump(mode="json")

    async def context(self, args: ContextArguments):
        query = ContextQuery(
            **args.model_dump(exclude={"as_of"}),
            as_of=args.as_of or datetime.now(UTC),
            project_id=self.project_for(args.scope),
        )
        async with self.client() as client:
            data = await self.request(
                client, "POST", "/v1/retrieval/context", query.model_dump(mode="json")
            )
        result = self.parse(ContextResult, data)
        if (
            not result.items
            or len(result.items) > args.limit
            or result.items[0].role != "seed"
            or result.items[0].memory_id != args.memory_id
            or result.as_of != query.as_of
            or (
                args.expected_version is not None
                and result.items[0].version_number != args.expected_version
            )
            or len({entry.version_id for entry in result.items}) != len(result.items)
        ):
            raise GatewayError("Memory service returned an invalid response.")
        history_sources = {result.items[0].version_id}
        for index, entry in enumerate(result.items):
            in_scope = entry.scope == args.scope or (
                args.scope == Scope.PROJECT
                and args.include_developer
                and entry.scope == Scope.DEVELOPER
            )
            if (
                not in_scope
                or (entry.scope == Scope.PROJECT and entry.project_id != self.settings.project_id)
                or any(args.conditions.get(k) != v for k, v in entry.conditions.items())
            ):
                raise GatewayError("Memory service returned a result outside the requested scope.")
            if entry.role == "historical":
                if (
                    not args.include_history
                    or entry.memory_id != args.memory_id
                    or entry.relation != "supersedes"
                    or entry.edge_target_version_id != entry.version_id
                    or entry.edge_source_version_id not in history_sources
                    or entry.applicable_at_query
                    or entry.status != "SUPERSEDED"
                    or entry.valid_to is None
                    or entry.valid_to > result.as_of
                ):
                    raise GatewayError("Memory service returned an invalid response.")
            elif (
                not entry.applicable_at_query
                or entry.valid_from > result.as_of
                or (entry.valid_to is not None and entry.valid_to <= result.as_of)
            ):
                raise GatewayError("Memory service returned an invalid response.")
            if index == 0:
                if (
                    entry.relation is not None
                    or entry.edge_source_version_id is not None
                    or entry.edge_target_version_id is not None
                ):
                    raise GatewayError("Memory service returned an invalid response.")
            elif entry.role != "historical":
                if (
                    entry.role != "conflicting"
                    or entry.relation != "contradicts"
                    or entry.verification != "uncertain"
                    or {entry.edge_source_version_id, entry.edge_target_version_id}
                    != {result.items[0].version_id, entry.version_id}
                ):
                    raise GatewayError("Memory service returned an invalid response.")
            if not args.verify_conflicts and entry.evidence_check != "not_requested":
                raise GatewayError("Memory service returned an invalid response.")
            if entry.role == "historical":
                history_sources.add(entry.version_id)
        return result.model_dump(mode="json")

    async def inspection(self, client: httpx.AsyncClient, args: MemoryReference):
        data = await self.request(client, "GET", f"/v1/memories/{args.memory_id}")
        result = self.parse(InspectionResponse, data)
        self.guard(result.memory)
        return result

    async def inspect(self, args: MemoryReference):
        async with self.client() as client:
            return (await self.inspection(client, args)).model_dump(mode="json")

    async def update(self, args: UpdateArguments):
        body = UpdateMemory(
            **args.model_dump(exclude={"source", "memory_id"}), source=self.source(args.source)
        ).model_dump(mode="json")
        async with self.client() as client:
            await self.inspection(client, args)
            data = await self.request(client, "PUT", f"/v1/memories/{args.memory_id}", body)
        result = self.parse(MemoryResponse, data)
        self.guard(result)
        return result.model_dump(mode="json")

    async def forget(self, args: MemoryReference):
        async with self.client() as client:
            await self.inspection(client, args)
            await self.request(client, "DELETE", f"/v1/memories/{args.memory_id}")
        return {"forgotten": True, "memory_id": str(args.memory_id)}

    async def retire(self, args: RetireArguments):
        async with self.client() as client:
            inspected = await self.inspection(client, args)
            body = RetireMemory(
                expected_version=args.expected_version,
                scope=inspected.memory.scope,
                project_id=inspected.memory.project_id,
            )
            data = await self.request(
                client,
                "POST",
                f"/v1/memories/{args.memory_id}/retire",
                body.model_dump(mode="json"),
            )
        result = self.parse(LifecycleResult, data)
        self.guard(result.memory)
        if result.memory.id != args.memory_id or result.retired_at is None:
            raise GatewayError("Memory service returned an invalid lifecycle response.")
        return result.model_dump(mode="json")

    async def restore(self, args: RestoreArguments):
        async with self.client() as client:
            inspected = await self.inspection(client, args)
            body = RestoreMemory(
                expected_version=args.expected_version,
                source_version=args.source_version,
                source=self.source(args.source),
                scope=inspected.memory.scope,
                project_id=inspected.memory.project_id,
            )
            data = await self.request(
                client,
                "POST",
                f"/v1/memories/{args.memory_id}/restore",
                body.model_dump(mode="json"),
            )
        result = self.parse(LifecycleResult, data)
        self.guard(result.memory)
        if result.memory.id != args.memory_id or result.retired_at is not None:
            raise GatewayError("Memory service returned an invalid lifecycle response.")
        return result.model_dump(mode="json")

    async def status(self, args: NoArguments):
        async with self.client() as client:
            data = await self.request(client, "GET", "/health/ready")
        if data != {"status": "ready"}:
            raise GatewayError("Memory service returned an invalid readiness response.")
        return {
            "status": "ready",
            "project_id": self.settings.project_id,
            "agent_id": self.settings.agent_id,
            "session_id": self.settings.session_id,
            "retrieval": "lexical",
        }
