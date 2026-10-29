import json

import pytest

from scripts.benchmark_memory_pipeline import evaluate, main, metrics, percentiles, summarize


def test_metrics_keep_no_match_and_empty_return_denominators_honest():
    assert metrics([], []) == {
        "precision_at_returned": None,
        "recall_at_limit": None,
        "reciprocal_rank": None,
        "correct_abstention": True,
    }
    assert metrics([], ["db"])["recall_at_limit"] == 0
    result = metrics(["noise", "db"], ["db", "other"])
    assert result["precision_at_returned"] == result["recall_at_limit"] == 0.5
    assert result["reciprocal_rank"] == 0.5
    assert metrics(["noise"], [])["correct_abstention"] is False
    with pytest.raises(ValueError, match="Duplicate"):
        metrics(["db", "db"], ["db"])


def test_nearest_rank_percentiles_and_summary_disclose_denominators():
    assert percentiles([10, 30, 20]) == {"samples": 3, "p50_ms": 20, "p95_ms": 30}
    base = {"partition": "design", "mode": "keyword", "elapsed_ms": [1, 2], "response_bytes": 100}
    result = summarize([{**base, **metrics([], [])}, {**base, **metrics(["db"], ["db"])}])[0]
    assert result["recall_at_limit"] == {"mean": 1.0, "defined_cases": 1}
    assert result["correct_abstention"] == {"mean": 1.0, "defined_cases": 1}
    assert result["latency"]["samples"] == 4


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://127.0.0.1/contextbridge",
        "sqlite:///contextbridge_test",
    ],
)
def test_non_test_or_non_postgresql_store_is_rejected_before_connecting(url):
    with pytest.raises(ValueError, match="dedicated PostgreSQL test"):
        evaluate(url, {})


def test_cli_never_overwrites_evidence_or_echoes_database_credentials(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "report.json"
    output.write_text("existing evidence")
    assert main(["--output", str(output)]) == 1
    assert output.read_text() == "existing evidence"
    output.unlink()
    monkeypatch.setenv("CONTEXTBRIDGE_TEST_DATABASE_URL", "invalid-secret-value")
    assert main(["--output", str(output)]) == 1
    assert "invalid-secret-value" not in capsys.readouterr().out
    assert not output.exists()


def test_cli_failed_design_checks_produce_inspectable_report_and_failure_exit(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CONTEXTBRIDGE_TEST_DATABASE_URL", "synthetic-test-store")
    monkeypatch.setattr(
        "scripts.benchmark_memory_pipeline.evaluate",
        lambda *a, **k: {
            "rows": [],
            "all_design_checks_pass": False,
        },
    )
    output = tmp_path / "failed.json"
    assert main(["--output", str(output)]) == 1
    assert json.loads(output.read_text())["all_design_checks_pass"] is False
