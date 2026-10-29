import pytest

from contextbridge.contracts import RetrievalQuery
from contextbridge.engine.query_understanding import AuthorizedQueryContext, understand
from tests.integration.retrieval_fakes import query


def interpret(text, context=None, **kwargs):
    request = RetrievalQuery.model_validate(query(query=text, **kwargs))
    before = request.model_dump()
    result = understand(request, developer_id="developer-a", context=context)
    assert request.model_dump() == before
    return result


def test_database_topic_current_state_and_release_label_require_explicit_filter():
    result = interpret("What DB are we using for V1?")
    assert result.topics == ("database",) and result.intent == "current_state"
    assert result.warnings == ("QUERY_VERSION_FILTER_REQUIRED",)
    assert not interpret("What DB are we using for V1?", conditions={"version": "V1"}).warnings


def test_explicit_conditions_time_project_and_identifiers_are_preserved():
    result = interpret(
        "Current SQLite for project contextbridge using db_v1.sqlite",
        conditions={"environment": "production"},
        as_of="2026-10-10T00:00:00Z",
    )
    assert result.intent == "historical" and not result.warnings


@pytest.mark.parametrize(
    "context",
    [
        None,
        AuthorizedQueryContext("developer-b", "project", "contextbridge", ("database",)),
        AuthorizedQueryContext("developer-a", "project", "elsewhere", ("database",)),
        AuthorizedQueryContext("developer-a", "developer", None, ("database",)),
        AuthorizedQueryContext("developer-a", "project", "contextbridge", ("database", "cache")),
    ],
)
def test_unbound_or_ambiguous_reference_never_uses_other_context(context):
    assert interpret("Are we using it now?", context).needs_clarification


def test_reference_can_resolve_only_one_authorized_topic_without_rewriting_query():
    context = AuthorizedQueryContext("developer-a", "project", "contextbridge", ("database",))
    result = interpret("Are we using it now?", context)
    assert result.resolved_reference == "database" and not result.warnings


@pytest.mark.parametrize(
    "text,warning",
    [
        ("What DB last month?", "QUERY_TIME_FILTER_REQUIRED"),
        ("What DB for V1?", "QUERY_VERSION_FILTER_REQUIRED"),
        ("What is the port?", "QUERY_TOPIC_CLARIFICATION_REQUIRED"),
        ("What database for project elsewhere?", "QUERY_PROJECT_CLARIFICATION_REQUIRED"),
    ],
)
def test_ambiguous_filters_and_terms_defer(text, warning):
    assert warning in interpret(text).warnings


def test_conflicting_release_does_not_override_explicit_condition():
    assert interpret("SQLite for V1", conditions={"version": "V2"}).needs_clarification


def test_reference_substrings_in_identifiers_are_not_pronouns():
    assert not interpret("Use src/it.py database config").warnings


def test_version_identifiers_and_routes_are_not_release_filters():
    assert not interpret("/v1/memories and docs/v2.md database lookup").warnings
