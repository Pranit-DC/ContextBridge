"""Float32 vector validation and pgvector SQL casts, without a model SDK."""

import hashlib
import math
import struct

from sqlalchemy import select, text
from sqlalchemy.types import UserDefinedType

from contextbridge.engine.errors import ModuleError


class VectorSQL(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kwargs):
        return "vector"


def vector32(values, *, code="INVALID_INPUT"):
    try:
        result = [struct.unpack("f", struct.pack("f", value))[0] for value in values]
    except (OverflowError, TypeError, struct.error):
        raise ModuleError(code) from None
    if not all(math.isfinite(value) for value in result) or not any(result):
        raise ModuleError(code)
    return result


def content_fingerprint(content):
    return hashlib.sha256(content.encode()).hexdigest()


def vector_available(session):
    return session.scalar(
        select(text("EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')"))
    )
