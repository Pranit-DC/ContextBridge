"""Explicit bounded backfill; never sends memory content to a model."""

import argparse
import json
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from contextbridge.config import Settings
from contextbridge.db import make_engine, make_session_factory
from contextbridge.engine.errors import EngineError
from contextbridge.persistence.related import backfill
from contextbridge.security import contains_secret


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    boundary = parser.add_mutually_exclusive_group(required=True)
    boundary.add_argument("--project-id")
    boundary.add_argument("--developer", action="store_true")
    parser.add_argument("--after", type=UUID)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    engine = None
    try:
        if args.project_id is not None and (
            not args.project_id.strip()
            or len(args.project_id) > 128
            or contains_secret(args.project_id)
        ):
            raise ValueError
        if not 1 <= args.limit <= 100:
            raise ValueError
        settings = Settings()
        engine = make_engine(settings)
        with make_session_factory(engine)() as session:
            result = backfill(
                session,
                settings.developer_id,
                scope="developer" if args.developer else "project",
                project_id=args.project_id,
                after=args.after,
                limit=args.limit,
            )
        print(json.dumps(result))
        return 0
    except (ValueError, EngineError):
        print("Related-memory backfill failed: INVALID_INPUT")
        return 1
    except SQLAlchemyError:
        print("Related-memory backfill failed: STORAGE_UNAVAILABLE")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
