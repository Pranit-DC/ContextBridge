"""Safety and reproducibility of the real-store, offline #8 comparison."""

import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.models import Memory
from scripts.evaluate_related_links import CASES, evaluate
from tests.integration.retrieval_fakes import create

pytestmark = pytest.mark.integration


def test_related_comparison_matches_design_cases_and_cleans_up(database):
    report = evaluate(database[0], json.loads(CASES.read_text()))
    assert report["matching_design_cases"] == report["case_count"] == 8
    assert report["hosted_requests"] == 0
    assert report["independent_review_complete"] is False
    assert report["semantic_quality_measured"] is False
    with Session(database[1]) as session:
        assert session.scalar(select(func.count()).select_from(Memory)) == 0


def test_evaluation_refuses_existing_records_without_altering_them(database):
    saved = create(database)
    with pytest.raises(ValueError, match="empty"):
        evaluate(database[0], json.loads(CASES.read_text()))
    with Session(database[1]) as session:
        assert session.get(Memory, saved.id) is not None
        assert session.scalar(select(func.count()).select_from(Memory)) == 1


def test_evaluation_rejects_non_test_database_before_connecting():
    with pytest.raises(ValueError, match="dedicated test"):
        evaluate("postgresql+psycopg://127.0.0.1/contextbridge", {})
