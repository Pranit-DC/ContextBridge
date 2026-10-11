import hashlib

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def lock_owner(session: Session, developer_id: str):
    """One ordering for capture, automated mutations, and explicit deletion."""
    digest = hashlib.sha256(f"contextbridge.capture:{developer_id}".encode()).digest()
    key = int.from_bytes(digest[:8], byteorder="big", signed=True)
    session.execute(select(func.pg_advisory_xact_lock(key)))
