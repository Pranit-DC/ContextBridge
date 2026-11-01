"""Grounding regressions with injected providers, separate from actual model measurements."""

import copy
import json
from types import SimpleNamespace

import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.providers.grounded import BatchVerifier, GroundedProvider
from contextbridge.formation.providers.quota import ObservedReservations, TokenGate, reservation
from scripts.formation.evaluate import ROOT, Annotations, fixture_run, load_dataset, score
from tests.formation.test_groq_provider import Clock, settings


def wire(candidate):
    return {
        "text": candidate["content"],
        "kind": candidate["type"],
        "conditions": [{"key": k, "value": v} for k, v in candidate["conditions"].items()],
        "effective_from": candidate["valid_from"],
        "key": candidate["claim_key"],
        "confidence": candidate["confidence"],
        "usefulness": candidate["usefulness"],
        "message_id": candidate["evidence_refs"][0]["message_id"],
        "evidence": candidate["source"]["evidence"],
    }


def check(candidate, **changes):
    return {
        "index": 0,
        "support": "supported",
        "scope": "bound",
        "kind": candidate["type"],
        "conditions": [{"key": k, "value": v} for k, v in candidate["conditions"].items()],
    } | changes


def client(responses):
    values, sent = iter(responses), []

    def complete(model, prompt, payload, schema):
        sent.append(copy.deepcopy(payload))
        return json.dumps(next(values))

    return SimpleNamespace(settings=settings(), complete=complete), sent


def test_compact_claims_keep_binding_and_batch_verdict_reused_in_admission(
    event, candidate, context
):
    fake, sent = client([{"claims": [wire(candidate)]}, {"checks": [check(candidate)]}])
    verifier = BatchVerifier(fake)
    produced = Extractor(GroundedProvider(fake), verifier).extract(event)
    assert produced[0]["event_id"] == event["event_id"]
    assert produced[0]["project_id"] == event["project_id"]
    assert produced[0]["source"] == candidate["source"]
    assert (
        AdmissionPolicy(verifier, lambda _: event).assess(produced[0], context)["outcome"]
        == "ADMIT"
    )
    assert len(sent) == 2


@pytest.mark.parametrize("fault", ["kind", "conditions", "other", "ambiguous", "unsupported"])
def test_supported_flag_cannot_override_wrong_metadata_or_scope(fault, event, candidate):
    changes = {
        "kind": {"kind": "FACT" if candidate["type"] != "FACT" else "DECISION"},
        "conditions": {"conditions": [{"key": "version", "value": "V8"}]},
        "other": {"scope": "other"},
        "ambiguous": {"scope": "ambiguous"},
        "unsupported": {"support": "unsupported"},
    }[fault]
    fake, _ = client([{"claims": [wire(candidate)]}, {"checks": [check(candidate, **changes)]}])
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        Extractor(GroundedProvider(fake), BatchVerifier(fake)).extract(event)


def test_omitted_condition_detected_from_independent_audit(event, candidate):
    required = [{"key": "version", "value": "V8"}]
    event["messages"][0]["content"] = "For this project V8, use PostgreSQL only for V8."
    candidate["source"]["evidence"] = event["messages"][0]["content"]
    candidate["conditions"] = {}
    fake, _ = client(
        [{"claims": [wire(candidate)]}, {"checks": [check(candidate, conditions=required)]}]
    )
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        Extractor(GroundedProvider(fake), BatchVerifier(fake)).extract(event)


def test_explicit_other_project_rejected_locally_even_if_model_would_claim_support(
    event, candidate
):
    event["messages"][0]["content"] = (
        f"Another unnamed repo uses MySQL; it is not {event['project_id']}."
    )
    candidate["content"] = "The other repository uses MySQL."
    candidate["source"]["evidence"] = "Another unnamed repo uses MySQL"
    fake, sent = client([{"claims": [wire(candidate)]}])
    assert Extractor(GroundedProvider(fake), BatchVerifier(fake)).extract(event) == []
    assert sent == []  # Explicit source exclusion abstains before any model request.
    assert BatchVerifier(fake).verify(candidate, event) == "unsupported"
    assert sent == []


def test_scope_exclusion_guard_keeps_valid_positive_and_version_qualified_claims(event):
    from contextbridge.formation.providers.grounded import outside_bound_project

    name = event["project_id"]
    event["messages"][0]["content"] = f"For {name} V1 use SQLite, not {name} V2."
    assert not outside_bound_project(event)
    event["messages"][0]["content"] = f"{name} uses PostgreSQL. That other repo is not {name}."
    assert not outside_bound_project(event)


@pytest.mark.parametrize("suffix", ["", " only offline", " but not in production", " and SQLite"])
def test_local_duplicate_shortcut_requires_the_complete_unqualified_assertion(
    suffix, candidate, record
):
    from contextbridge.formation.providers.grounded import BoundedDuplicateVerifier

    project = candidate["project_id"]
    candidate["content"] = f"Use PostgreSQL as the primary database for {project}" + suffix + "."
    candidate["claim_key"] = "project.database.primary"
    memory = record["memory"]
    memory.update(
        scope=candidate["scope"],
        project_id=project,
        type=candidate["type"],
        conditions=candidate["conditions"],
    )
    memory["version"]["content"] = f"PostgreSQL is the primary store for {project}."
    record["claim_key"] = candidate["claim_key"]
    fake, sent = client([{"relation": "different"}])
    relation = BoundedDuplicateVerifier(fake).compare(candidate, [record])
    assert relation == ("different" if suffix else "equivalent")
    assert bool(sent) == bool(suffix)


@pytest.mark.parametrize("fault", ["unknown_message", "quote", "extra_binding", "duplicate"])
def test_bad_wire_provenance_rejected_before_audit(fault, event, candidate):
    proposed = wire(candidate)
    if fault == "unknown_message":
        proposed["message_id"] = "missing"
    elif fault == "quote":
        proposed["evidence"] = "Not in the source"
    elif fault == "extra_binding":
        proposed["project_id"] = "other"
    fake, sent = client([{"claims": [proposed, proposed] if fault == "duplicate" else [proposed]}])
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        Extractor(GroundedProvider(fake), BatchVerifier(fake)).extract(event)
    assert len(sent) == 1


@pytest.mark.parametrize("indices", [[], [0, 0], [1]])
def test_batch_audit_must_cover_each_actual_candidate_once(indices, event, candidate):
    fake, _ = client(
        [
            {"claims": [wire(candidate)]},
            {"checks": [check(candidate, index=i) for i in indices]},
        ]
    )
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        Extractor(GroundedProvider(fake), BatchVerifier(fake)).extract(event)


def test_two_candidates_use_one_batch_audit_without_losing_a_claim():
    from scripts.formation.evaluate import fixture_candidate

    d, _ = load_dataset("tuning", root=ROOT / "fresh-v2-20261012")
    case = next(c for c in d.cases if len(c.expected_claims) == 2)
    event = case.event.model_dump(mode="json")
    candidates = [fixture_candidate(case, c).model_dump(mode="json") for c in case.expected_claims]
    fake, sent = client(
        [
            {"claims": [wire(c) for c in candidates]},
            {"checks": [check(c, index=i) for i, c in enumerate(candidates)]},
        ]
    )
    assert len(Extractor(GroundedProvider(fake), BatchVerifier(fake)).extract(event)) == 2
    assert len(sent) == 2


def test_explicit_adopted_database_type_is_canonicalized_without_rewriting_claim(event, candidate):
    name = event["project_id"]
    event["messages"][0]["content"] = (
        f"For {name}, use PostgreSQL as the primary database. We have already agreed this."
    )
    candidate.update(
        type="FACT",
        content=f"Use PostgreSQL as the primary database for {name}.",
        claim_key="project.database.primary",
    )
    candidate["source"]["evidence"] = event["messages"][0]["content"]
    fake, _ = client(
        [{"claims": [wire(candidate)]}, {"checks": [check(candidate, kind="DECISION")]}]
    )
    provider = GroundedProvider(fake)
    result = Extractor(provider, BatchVerifier(fake)).extract(event)
    assert result[0]["type"] == "DECISION"
    assert result[0]["content"] == candidate["content"]
    assert result[0]["source"]["evidence"] == candidate["source"]["evidence"]
    assert provider.type_corrections == 1


def test_explicit_database_source_cannot_be_changed_to_a_different_value(event, candidate):
    name = event["project_id"]
    event["messages"][0]["content"] = f"For {name}, use PostgreSQL as the primary database."
    candidate.update(
        content=f"Use SQLite as the primary database for {name}.",
        claim_key="project.database.primary",
    )
    candidate["source"]["evidence"] = event["messages"][0]["content"]
    fake, sent = client([{"claims": [wire(candidate)]}])
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        GroundedProvider(fake).generate(event)
    assert len(sent) == 1


@pytest.mark.parametrize("kind", ["STATE", "EVENT"])
def test_literal_category_and_time_survive_a_weak_models_fact_tag(kind, event, candidate):
    name = event["project_id"]
    quote = (
        f"{name} release branch is currently frozen for feature changes."
        if kind == "STATE"
        else f"{name} backup restore finished successfully at 2026-10-08T07:20:00Z."
    )
    event["messages"][0]["content"] = quote
    candidate.update(type="FACT", content=quote, claim_key=None)
    candidate["source"]["evidence"] = quote
    fake, _ = client([{"claims": [wire(candidate)]}, {"checks": [check(candidate)]}])
    provider = GroundedProvider(fake)
    result = Extractor(provider, BatchVerifier(fake)).extract(event)[0]
    assert result["type"] == kind
    assert result["content"] == quote
    assert provider.type_corrections == 1
    if kind == "EVENT":
        assert result["valid_from"] == "2026-10-08T07:20:00Z"
        assert provider.time_corrections == 1


@pytest.mark.parametrize(
    "prefix", ["wasn't completed", "might have completed", "will be completed"]
)
def test_literal_event_projection_never_establishes_negated_or_speculative_occurrence(prefix):
    from contextbridge.formation.providers.grounded import literal_metadata

    quote = f"Cedar backup {prefix} at 2026-10-08T07:20:00Z."
    assert literal_metadata(quote, quote, "cedar", "tool") == (None, None)


def test_speculation_preflight_never_discards_an_established_fact_in_another_message(event):
    from contextbridge.formation.providers.grounded import uncertain_only

    name = event["project_id"]
    event["messages"][0]["content"] = (
        f"{name} might migrate its cache someday; there is no chosen replacement or effective date."
    )
    assert uncertain_only(event)
    event["messages"].append(
        {"message_id": "actual", "role": "user", "content": f"{name} uses Redis."}
    )
    assert not uncertain_only(event)


def test_batch_cache_never_accepts_changed_claim_or_event(event, candidate):
    fake, sent = client(
        [{"checks": [check(candidate)]}, {"checks": [check(candidate, support="unsupported")]}]
    )
    verifier = BatchVerifier(fake)
    assert verifier.verify(candidate, event) == "supported"
    candidate["content"] = "Invented different claim"
    assert verifier.verify(candidate, event) == "unsupported"
    assert len(sent) == 2


def test_compaction_never_hides_a_known_key_in_source_metadata(event):
    from tests.formation.test_groq_provider import KEY

    event["agent"] = KEY
    fake, sent = client([])
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        GroundedProvider(fake).generate(event)
    assert sent == []


def test_direct_batch_verifier_screens_fields_omitted_from_wire(event, candidate):
    from tests.formation.test_groq_provider import KEY

    candidate["claim_key"] = KEY
    fake, sent = client([])
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        BatchVerifier(fake).verify(candidate, event)
    assert sent == []


def test_input_estimate_uses_known_model_profile_and_full_new_payload(event):
    from contextbridge.formation.providers.grounded import EXTRACTION, Claims

    cfg, estimator = settings(max_output_tokens=1024), ObservedReservations()
    full = reservation(cfg, EXTRACTION, event, Claims)
    assert estimator.estimate(cfg, cfg.model, EXTRACTION, event, Claims) == full
    estimator.observe(
        cfg, cfg.model, EXTRACTION, Claims, SimpleNamespace(model=cfg.model, input_tokens=700)
    )
    estimated = estimator.estimate(cfg, cfg.model, EXTRACTION, event, Claims)
    assert estimated == min(
        full, 700 + len(json.dumps(event, ensure_ascii=False).encode()) + 1024 + 512
    )
    assert estimator.estimate(cfg, cfg.model, EXTRACTION + " changed", event, Claims) > estimated
    assert all(type(v) is int for v in estimator.inputs.values())
    estimator.observe(cfg, cfg.model, EXTRACTION, Claims, None)
    assert estimator.estimate(cfg, cfg.model, EXTRACTION, event, Claims) == full


def test_smoothed_quota_still_honors_budget_window_and_serial_start_spacing():
    clock = Clock()
    gate = TokenGate(clock=clock.clock, sleeper=clock.sleep, smooth=True)
    gate.pending_tokens = 3000
    gate.wait()
    gate.observe(SimpleNamespace(input_tokens=500, output_tokens=100))
    gate.wait()
    assert clock.now >= 600 * 61 / 5000 and clock.now >= 3.1
    assert gate.total == 3600


def test_provisional_labels_cannot_be_reported_as_independent_human_quality():
    dataset, digest = load_dataset("tuning")
    run, labels = fixture_run(dataset, digest)
    run.mode = "model_predictions"
    run.metadata.provider_id = "recorded-no-live-model"
    run.metadata.model_id = "synthetic"
    run.metadata.prompt_version = "synthetic"
    run.metadata.recorded_at = dataset.cases[0].event.occurred_at
    from scripts.formation.evaluate import dataset_digest

    labels = Annotations.model_validate(
        labels.model_dump()
        | {
            "label_source": "agent_proposed",
            "run_sha256": dataset_digest(run),
        }
    )
    report = score(dataset, digest, run, labels)
    assert report["results_kind"] == "provisional_agent_prediction_counts"
    assert report["independent_review_complete"] is False
    assert report["quality_gate"] == "pending"
