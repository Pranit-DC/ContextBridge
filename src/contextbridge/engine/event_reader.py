"""Authorized, retention-aware event lookup for an injected formation policy."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from contextbridge.engine.errors import ModuleError
from contextbridge.engine.ingestion import IngestionService
from contextbridge.models import CaptureEvent


class EventReader:
    def __init__(self, sessions, settings):
        self.sessions, self.settings = sessions, settings

    def __call__(self, event_id):
        try:
            event_id = UUID(str(event_id))
        except (ValueError, TypeError):
            return None
        try:
            with self.sessions() as session:
                ingestion = IngestionService(session, self.settings)
                ingestion.expire()
                row = session.scalar(
                    select(CaptureEvent).where(
                        CaptureEvent.event_id == event_id,
                        CaptureEvent.developer_id == self.settings.developer_id,
                        ingestion.scope_filter(),
                        CaptureEvent.payload.is_not(None),
                    )
                )
                return row.payload if row is not None else None
        except SQLAlchemyError:
            raise ModuleError("STORAGE_UNAVAILABLE", retryable=True) from None
