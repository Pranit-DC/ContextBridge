import pytest

from contextbridge.inspection.viewmodel import (
    detail_from,
    plain,
    row_from,
    rows_from_browse,
)
from tests.inspection.fakes import browse_result, inspection, memory, version

RLO = "‮"


def test_plain_removes_control_zero_width_and_direction_characters():
    dirty = f"ab{RLO}cd​ef\x00gh\x1b[31m﻿ij"
    assert plain(dirty) == "abcdefgh[31mij"


def test_plain_keeps_newlines_tabs_and_ordinary_unicode():
    assert plain("line one\nline\ttwo — café 日本") == "line one\nline\ttwo — café 日本"


def test_plain_does_not_interpret_html_or_markdown():
    text = "<script>alert(1)</script> [link](http://x) **bold** ![img](http://y)"
    assert plain(text) == text  # shown literally by a text widget, never rendered


def test_plain_truncates_with_an_ellipsis():
    assert plain("a" * 50, 10) == "a" * 9 + "…"
    assert plain("short", 10) == "short"


def test_row_uses_ordinary_language():
    row = row_from(memory(conditions={"environment": "production"}))
    assert (row.type_label, row.status_label) == ("Decision", "Current")
    assert row.scope_label == "Project contextbridge"
    assert row.conditions == "Applies when environment is production"
    assert row.validity == "Since 2026-10-09 10:00 UTC"
    assert (
        row.source == "A user statement, recorded by codex-pranit "
        "(session session-1, interaction interaction-1)"
    )
    assert row.uncertainty is None


def test_unconditional_developer_memory_and_replaced_version_labels():
    row = row_from(memory(scope="developer", status="SUPERSEDED", valid_to="2026-10-12T09:30:00Z"))
    assert row.scope_label == "All your projects"
    assert row.conditions == "Applies everywhere"
    assert row.status_label == "Replaced"
    assert row.validity == "2026-10-09 10:00 UTC to 2026-10-12 09:30 UTC"


@pytest.mark.parametrize(
    ("state", "confidence", "expected"),
    [
        ("contested", 0.99, "Disputed"),
        ("clear", 0.3, "Lower confidence"),
        ("clear", 0.7, None),
        ("clear", None, None),
    ],
)
def test_uncertainty_is_shown_for_disputes_and_low_confidence(state, confidence, expected):
    row = row_from(memory(), state, confidence)
    if expected is None:
        assert row.uncertainty is None
    else:
        assert row.uncertainty.startswith(expected)


def test_browse_rows_carry_each_items_uncertainty():
    items = browse_result(memory(), decision_state="contested")["items"]
    assert rows_from_browse(items)[0].uncertainty.startswith("Disputed")


def test_long_content_is_shortened_in_rows_but_complete_in_detail():
    mem = memory("x" * 1000)
    assert len(row_from(mem).text) == 400
    assert len(detail_from(inspection(mem)).current.content) == 1000


def test_detail_lists_history_newest_first_with_evidence_and_a_plain_relationship():
    v1 = version("uses PostgreSQL", number=1, status="SUPERSEDED", valid_to="2026-10-10T00:00:00Z")
    mem = memory("uses SQLite", number=2, valid_from="2026-10-10T00:00:00Z")
    edges = [
        {
            "from_version_id": mem["version"]["id"],
            "to_version_id": v1["id"],
            "relation": "supersedes",
        }
    ]
    detail = detail_from(inspection(mem, history=[v1, mem["version"]], edges=edges))
    assert [v.number for v in detail.history] == [2, 1]
    assert detail.current.number == 2 and detail.expected_version == 2
    assert detail.history[1].status_label == "Replaced"
    assert detail.history[1].evidence and detail.history[0].evidence
    assert detail.relationships == ["Version 2 replaced version 1."]


def test_edges_to_unknown_versions_are_ignored():
    mem = memory()
    edges = [
        {
            "from_version_id": mem["version"]["id"],
            "to_version_id": "99999999-9999-4999-8999-999999999999",
            "relation": "supersedes",
        }
    ]
    assert detail_from(inspection(mem, edges=edges)).relationships == []


def test_a_missing_history_still_shows_the_current_version():
    mem = memory()
    detail = detail_from({"memory": mem, "history": [], "edges": []})
    assert detail.current.number == 1 and len(detail.history) == 1


def test_evidence_and_content_are_sanitized_in_the_detail_view():
    mem = memory(f"claim{RLO}", evidence=f"proof\x00{RLO}<b>text</b>")
    detail = detail_from(inspection(mem))
    assert RLO not in detail.current.content
    assert detail.current.evidence == "proof<b>text</b>"
