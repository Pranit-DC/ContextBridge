"""Bounded query interpretation. Annotations never rewrite text or inferred access filters."""

import re
from dataclasses import dataclass

TOPICS = {
    "database": r"\b(database|db|sqlite|postgres(?:ql)?|mysql)\b",
    "runtime": r"\b(runtime|python|node(?:js)?|typescript)\b",
    "cache": r"\b(cache|redis|memcached)\b",
    "api": r"\b(api|endpoint|http)\b",
}
REFERENCE = re.compile(
    r"(?<![\w./-])(it|that|this choice|the former|the latter)(?![\w/-]|\.\w)", re.I
)
CURRENT = re.compile(r"\b(current(?:ly)?|now|are we using|do we use|is our|are using)\b", re.I)
HISTORICAL = re.compile(
    r"\b(previous(?:ly)?|formerly|used to|last (?:week|month|year)|yesterday)\b", re.I
)
VERSION = re.compile(r"(?<![\w./-])V\d+(?![\w/-]|\.\w)", re.I)
PROJECT_DESCRIPTORS = frozenset(
    {
        "database",
        "db",
        "runtime",
        "cache",
        "api",
        "configuration",
        "settings",
        "memory",
        "memories",
        "state",
        "status",
        "facts",
        "decisions",
        "dependencies",
        "history",
        "name",
        "scope",
        "preferences",
        "rules",
        "version",
    }
)


@dataclass(frozen=True)
class AuthorizedQueryContext:
    """Server-injected context, never loaded from another project or raw query text.

    The additive referenced-search adapter builds this from a freshly authorized
    explicitly selected memory. No global last-query or conversation cache is used.
    """

    developer_id: str
    scope: str
    project_id: str | None
    topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class Understanding:
    topics: tuple[str, ...]
    intent: str
    warnings: tuple[str, ...] = ()
    resolved_reference: str | None = None

    @property
    def needs_clarification(self):
        return bool(self.warnings)


def understand(query, *, developer_id, context=None):
    text = query.query
    topics = tuple(topic for topic, pattern in TOPICS.items() if re.search(pattern, text, re.I))
    intent = (
        "historical"
        if HISTORICAL.search(text) or query.as_of is not None
        else ("current_state" if CURRENT.search(text) else "general")
    )
    warnings, resolved = [], None
    if REFERENCE.search(text):
        authorized = (
            isinstance(context, AuthorizedQueryContext)
            and context.developer_id == developer_id
            and context.scope == query.scope
            and context.project_id == query.project_id
        )
        options = tuple(dict.fromkeys(context.topics)) if authorized else ()
        if len(options) == 1 and options[0] in TOPICS and not (topics and options[0] not in topics):
            resolved = options[0]
            topics = topics or options
        else:
            warnings.append("QUERY_REFERENCE_CLARIFICATION_REQUIRED")
    versions = set(match.upper() for match in VERSION.findall(text))
    if versions:
        explicit = query.conditions.get("version")
        if explicit is None:
            warnings.append("QUERY_VERSION_FILTER_REQUIRED")
        elif versions != {explicit.upper()}:
            warnings.append("QUERY_FILTER_CLARIFICATION_REQUIRED")
    if HISTORICAL.search(text) and query.as_of is None:
        warnings.append("QUERY_TIME_FILTER_REQUIRED")
    # A named project cannot replace the authorized binding, including developer-only calls.
    named = re.search(r"\bproject\s+([\"'`]?)([\w.-]+)", text, re.I)
    if named:
        label = named[2].casefold().rstrip(".")
        explicit_name = bool(named[1] or re.search(r"\bfor\s*$", text[: named.start()], re.I))
        if (explicit_name or label not in PROJECT_DESCRIPTORS) and label != (
            query.project_id or ""
        ).casefold():
            warnings.append("QUERY_PROJECT_CLARIFICATION_REQUIRED")
    # These short terms have common software/non-software meanings. Do not infer a topic.
    if not topics and re.search(r"\b(go|rust|port)\b", text, re.I):
        warnings.append("QUERY_TOPIC_CLARIFICATION_REQUIRED")
    return Understanding(topics, intent, tuple(dict.fromkeys(warnings)), resolved)
