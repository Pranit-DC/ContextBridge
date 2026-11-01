from typing import Literal, get_args

ErrorCode = Literal[
    "INVALID_INPUT",
    "OUT_OF_SCOPE",
    "PROVIDER_UNAVAILABLE",
    "INVALID_PROVIDER_OUTPUT",
    "EMBEDDING_UNAVAILABLE",
    "VERSION_CONFLICT",
    "CANCELLED",
    "STORAGE_UNAVAILABLE",
]


class ModuleError(Exception):
    """A safe public failure; never construct it with provider or SQL exception text."""

    def __init__(self, code: ErrorCode, *, retryable: bool = False):
        if code not in get_args(ErrorCode) or type(retryable) is not bool:
            code, retryable = "INVALID_PROVIDER_OUTPUT", False
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class EngineError(ModuleError):
    def __init__(self, code: ErrorCode, status_code: int, *, retryable: bool = False):
        super().__init__(code, retryable=retryable)
        self.status_code = status_code


class IngestionError(EngineError):
    pass
