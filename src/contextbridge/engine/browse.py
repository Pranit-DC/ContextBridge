import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from contextbridge.config import Settings
from contextbridge.contracts import BrowseQuery, BrowseResult
from contextbridge.engine.errors import EngineError
from contextbridge.models import Memory
from contextbridge.persistence.records import record_response, scoped_versions
from contextbridge.security import contains_secret_fields


class PageCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    after: UUID
    instant: AwareDatetime
    binding: str


class BrowseService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings

    def binding(self, query):
        payload = query.model_dump(mode="json", exclude={"cursor", "limit"})
        payload["owner"] = self.settings.developer_id
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def encode(self, cursor):
        raw = cursor.model_dump_json().encode()
        signature = hmac.digest(self.settings.api_token.get_secret_value().encode(), raw, "sha256")
        return base64.urlsafe_b64encode(signature + raw).decode().rstrip("=")

    def decode(self, query):
        try:
            raw = base64.b64decode(
                query.cursor + "=" * (-len(query.cursor) % 4), altchars=b"-_", validate=True
            )
            signature, payload = raw[:32], raw[32:]
            expected = hmac.digest(
                self.settings.api_token.get_secret_value().encode(), payload, "sha256"
            )
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            cursor = PageCursor.model_validate_json(payload)
            if not hmac.compare_digest(cursor.binding, self.binding(query)):
                raise ValueError
            return cursor
        except (ValueError, ValidationError, TypeError):
            raise EngineError("INVALID_INPUT", 422) from None

    def browse(self, query: BrowseQuery) -> BrowseResult:
        if contains_secret_fields(query.model_dump(mode="json")):
            raise EngineError("INVALID_INPUT", 422)
        cursor = self.decode(query) if query.cursor else None
        instant = cursor.instant if cursor else query.as_of or datetime.now(UTC)
        stmt = scoped_versions(
            self.settings.developer_id, query.scope, query.project_id, instant, query.conditions
        )
        if cursor:
            stmt = stmt.where(Memory.id > cursor.after)
        rows = self.session.execute(stmt.order_by(Memory.id).limit(query.limit + 1)).all()
        page = rows[: query.limit]
        next_cursor = None
        if len(rows) > query.limit:
            next_cursor = self.encode(
                PageCursor(after=page[-1][0].id, instant=instant, binding=self.binding(query))
            )
        return BrowseResult(
            schema_version=1, items=[record_response(*row) for row in page], next_cursor=next_cursor
        )
