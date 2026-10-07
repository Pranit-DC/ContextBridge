from contextlib import asynccontextmanager
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

from contextbridge.mcp_adapter.arguments import (
    Evidence,
    MemoryReference,
    NoArguments,
    SearchArguments,
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
