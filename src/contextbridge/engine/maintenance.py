"""Bounded raw-event retention for installations without the later worker scheduler."""

from sqlalchemy.exc import SQLAlchemyError

from contextbridge.config import Settings
from contextbridge.db import make_engine, make_session_factory
from contextbridge.engine.errors import IngestionError
from contextbridge.engine.ingestion import IngestionService


def main() -> int:
    try:
        settings = Settings()
    except ValueError:
        print("Capture expiry failed: INVALID_INPUT")
        return 1
    engine = make_engine(settings)
    try:
        with make_session_factory(engine)() as session:
            count = IngestionService(session, settings).expire()
        print(f"Expired capture buffers: {count}")
        return 0
    except IngestionError as exc:
        print(f"Capture expiry failed: {exc.code}")
        return 1
    except SQLAlchemyError:
        print("Capture expiry failed: STORAGE_UNAVAILABLE")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
