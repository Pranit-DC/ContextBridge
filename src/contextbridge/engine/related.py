"""Bounded, evidence-backed navigation links; never a semantic or truth judgment."""

import re

from contextbridge.security import contains_secret_fields

MAX_REFERENCES = 8
MAX_CANDIDATES = 100
MAX_LINKS = 8
CODE = re.compile(r"(?<!`)`([^`\s]{3,128})`(?!`)")
IDENTIFIER = re.compile(r"[A-Za-z0-9_./:@-]+")


def references(content, evidence):
    """Exact, case-sensitive code references present in both claim and evidence.

    Require a structured identifier/path or CamelCase name, not generic prose.
    No embeddings, model confidence, inferred claim labels or word overlap qualify.
    """
    if contains_secret_fields({"content": content, "evidence": evidence}):
        return ()

    def extract(text):
        return {
            token
            for token in CODE.findall(text)
            if IDENTIFIER.fullmatch(token)
            and any(character.isalpha() for character in token)
            and re.search(r"[/_.:@-]|[a-z][A-Z]", token)
        }

    return tuple(sorted(extract(content) & extract(evidence))[:MAX_REFERENCES])
