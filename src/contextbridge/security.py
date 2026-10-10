import re

# Screening is deliberately conservative, and is not a general secret detector.
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----", re.I),
    re.compile(
        r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"
    ),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{12,}", re.I),
    re.compile(
        r"[\"']?\b(?:api[_-]?key|password|passwd|access[_-]?token|client[_-]?secret)"
        r"\b[\"']?\s*[:=]\s*[\"']?[^\s\"',;}{]+",
        re.I,
    ),
    re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:]+:[^\s/@]+@", re.I),
)


def contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)
