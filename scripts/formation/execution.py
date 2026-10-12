"""Validate saved execution evidence offline; never infer attempts from case error codes."""

from collections import defaultdict
from math import isclose
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, FiniteFloat

from contextbridge.engine.errors import ErrorCode, ModuleError
from contextbridge.schemas import Identifier, StrictModel
from contextbridge.security import contains_secret_fields

Count = Annotated[int, Field(strict=True, ge=0, le=40)]
Tokens = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
Nonnegative = Annotated[FiniteFloat, Field(strict=True, ge=0)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Call(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    call_index: Annotated[int, Field(ge=1, le=40)]
    case_id: Identifier
    stage: Literal["extraction", "verification", "comparison"]
    requested_model: Identifier
    observed_model: Identifier | None
    error_code: ErrorCode | None
    retryable: bool
    latency_ms: Nonnegative
    input_tokens: Tokens | None
    output_tokens: Tokens | None
    cost_usd: Nonnegative | None
    http_status: Annotated[int, Field(ge=100, le=599)] | None = None
    reserved_tokens: Annotated[int, Field(ge=1, le=4_000_000)] | None = None
    provider_error_code: (
        Literal[
            "json_validate_failed",
            "invalid_request_error",
            "invalid_json_schema",
            "unsupported_parameter",
            "model_not_found",
            "model_decommissioned",
            "rate_limit_exceeded",
            "invalid_api_key",
            "permission_denied",
        ]
        | None
    ) = None


class CaseExecution(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: Identifier
    attempted_calls: Count
    execution: Literal[
        "attempted",
        "provider_stop",
        "call_budget",
        "token_budget",
        "local_only",
        "scope_abstention",
        "uncertain_abstention",
    ]
    required_tokens: Annotated[int, Field(ge=1, le=4_000_000)] | None = None
    type_corrections: Annotated[int, Field(strict=True, ge=0, le=100)] = 0
    time_corrections: Annotated[int, Field(strict=True, ge=0, le=100)] = 0


class ExecutionSettings(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    concurrency: Annotated[int, Field(ge=1, le=1)]
    request_interval_seconds: Annotated[FiniteFloat, Field(ge=3.1, le=60)]
    max_calls: Annotated[int, Field(ge=1, le=40)]
    automatic_retries: Annotated[int, Field(ge=0, le=0)]
    stop_on_provider_unavailable: bool
    tokens_per_minute: Annotated[int, Field(ge=128, le=8000)] | None = None
    max_total_tokens: Annotated[int, Field(ge=128, le=50000)] | None = None


class ExecutionTelemetry(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Annotated[int, Field(ge=1, le=1)]
    dataset_sha256: Digest
    run_sha256: Digest
    prompt_version: Identifier
    calls: list[Call] = Field(max_length=40)
    # Older sidecars recorded calls only; absent no-call evidence remains unknown.
    cases: list[CaseExecution] | None = Field(default=None, min_length=1, max_length=64)
    execution: ExecutionSettings | None = None


def reject_unless(condition):
    if not condition:
        raise ModuleError("INVALID_INPUT")


def matches(left, right):
    return (
        left is right
        if left is None or right is None
        else isclose(left, right, rel_tol=0, abs_tol=1e-6)
    )


def summarize_execution(dataset, digest, run, sidecar=None):
    # Imported lazily to keep the CLI modules independent during initialization.
    from scripts.formation.evaluate import dataset_digest, index_cases

    examples = {case.case_id: case for case in dataset.cases}
    predictions = index_cases(run.cases, examples)
    counts = dict(
        completed_network_cases=0,
        attempted_failed_network_cases=0,
        unattempted_cases=0,
        provider_stop_cases=0,
        call_budget_cases=0,
        local_only_cases=0,
        unknown_cases=0,
    )
    grouped = defaultdict(list)
    if run.metadata.configuration.get("scope_guard") == "explicit_exclusion":
        counts["scope_abstention_cases"] = 0
    if run.metadata.configuration.get("uncertainty_guard") == "no_adopted_choice":
        counts["uncertain_abstention_cases"] = 0
    recorded = {}
    if sidecar is not None:
        reject_unless(
            isinstance(sidecar, ExecutionTelemetry)
            and not contains_secret_fields(sidecar.model_dump(mode="json"))
            and run.mode == "model_predictions"
            and sidecar.dataset_sha256 == digest == dataset_digest(dataset) == run.dataset_sha256
            and sidecar.run_sha256 == dataset_digest(run)
            and sidecar.prompt_version == run.metadata.prompt_version
            and (sidecar.cases is None) == (sidecar.execution is None)
        )
        if sidecar.cases is not None:
            recorded = index_cases(sidecar.cases, examples)
            reject_unless(
                sidecar.execution.stop_on_provider_unavailable
                and len(sidecar.calls) <= sidecar.execution.max_calls
            )
            reject_unless(
                (sidecar.execution.tokens_per_minute is None)
                == (sidecar.execution.max_total_tokens is None)
            )
            if sidecar.execution.tokens_per_minute is not None:
                counts["token_budget_cases"] = 0
                reject_unless(all(call.reserved_tokens is not None for call in sidecar.calls))
        order = {case_id: index for index, case_id in enumerate(examples)}
        previous_case, stopped = -1, False
        for index, call in enumerate(sidecar.calls, 1):
            reject_unless(call.call_index == index and call.case_id in examples)
            reject_unless(order[call.case_id] >= previous_case)
            if sidecar.execution is not None:
                reject_unless(not stopped)
                stopped = call.error_code == "PROVIDER_UNAVAILABLE"
            previous_case = order[call.case_id]
            expected_model = (
                run.metadata.model_id
                if call.stage == "extraction"
                else run.metadata.configuration.get("verifier_model") or run.metadata.model_id
            )
            reject_unless(call.requested_model == expected_model)
            reject_unless(call.error_code is not None or not call.retryable)
            reject_unless(
                call.provider_error_code is None
                or call.http_status is not None
                and call.http_status != 200
            )
            if call.http_status is not None and call.http_status != 200:
                reject_unless(
                    call.error_code == "PROVIDER_UNAVAILABLE"
                    and call.retryable == (call.http_status == 429 or call.http_status >= 500)
                    and all(
                        value is None
                        for value in (
                            call.observed_model,
                            call.input_tokens,
                            call.output_tokens,
                            call.cost_usd,
                        )
                    )
                )
            if call.cost_usd is not None:
                reject_unless(run.metadata.cost_currency == "USD")
            grouped[call.case_id].append(call)

    output, prior_calls, provider_stopped = [], 0, False
    prior_tokens, token_stopped = 0, False
    for case_id, example in examples.items():
        prediction, calls = predictions[case_id], grouped[case_id]
        record = recorded.get(case_id)
        if record is not None:
            reject_unless(record.type_corrections <= len(prediction.proposals))
            reject_unless(record.time_corrections <= len(prediction.proposals))
            reject_unless(record.attempted_calls == len(calls))
            reject_unless((record.execution == "attempted") == bool(calls))
            reject_unless(record.execution == "token_budget" or record.required_tokens is None)
        if calls:
            comparisons = [call for call in calls[1:] if call.stage == "comparison"]
            verification = [call for call in calls[1:] if call.stage == "verification"]
            semantic = run.metadata.configuration.get("semantic_duplicate_verifier") is True
            batch = run.metadata.configuration.get("verification_mode") == "batch"
            reject_unless(not comparisons or semantic and bool(example.context.records))
            stages = [call.stage for call in calls[1:]]
            reject_unless(
                stages == ["verification"] * len(verification) + ["comparison"] * len(comparisons)
            )
            reject_unless(
                calls[0].stage == "extraction"
                and len(verification) <= len(prediction.proposals)
                and len(comparisons) <= len(prediction.proposals)
                and all(call.error_code is None for call in calls[:-1])
                and (calls[-1].error_code is None or calls[-1].error_code == prediction.error_code)
                and prediction.latency_ms is not None
                and prediction.latency_ms + 1e-6 >= sum(call.latency_ms for call in calls)
            )
            reject_unless(
                prediction.error_code is not None
                or len(verification)
                == (int(bool(prediction.proposals)) if batch else len(prediction.proposals))
            )
            for field, call_field in (
                ("input_tokens", "input_tokens"),
                ("output_tokens", "output_tokens"),
                ("cost", "cost_usd"),
            ):
                values = [getattr(call, call_field) for call in calls]
                total = sum(values) if all(value is not None for value in values) else None
                reject_unless(matches(getattr(prediction, field), total))
            category = (
                "completed_network_cases"
                if prediction.error_code is None
                else "attempted_failed_network_cases"
            )
        elif record is None:
            category = "unknown_cases"
        else:
            reject_unless(
                not prediction.proposals
                and not prediction.decisions
                and all(
                    getattr(prediction, field) is None
                    for field in ("latency_ms", "input_tokens", "output_tokens", "cost")
                )
            )
            if record.execution == "provider_stop":
                reject_unless(provider_stopped and prediction.error_code == "PROVIDER_UNAVAILABLE")
                reject_unless(prior_calls < sidecar.execution.max_calls)
                counts["provider_stop_cases"] += 1
                category = "unattempted_cases"
            elif record.execution == "call_budget":
                reject_unless(
                    prior_calls == sidecar.execution.max_calls
                    and prediction.error_code == "CANCELLED"
                )
                counts["call_budget_cases"] += 1
                category = "unattempted_cases"
            elif record.execution == "token_budget":
                limits = sidecar.execution
                reject_unless(
                    limits.tokens_per_minute is not None
                    and record.required_tokens is not None
                    and prediction.error_code == "CANCELLED"
                    and (
                        token_stopped
                        or record.required_tokens > limits.tokens_per_minute
                        or prior_tokens + record.required_tokens > limits.max_total_tokens
                    )
                )
                token_stopped = True
                counts["token_budget_cases"] += 1
                category = "unattempted_cases"
            elif record.execution == "scope_abstention":
                from contextbridge.formation.providers.grounded import outside_bound_project

                reject_unless(
                    run.metadata.configuration.get("scope_guard") == "explicit_exclusion"
                    and outside_bound_project(example.event.model_dump(mode="json"))
                    and prediction.error_code is None
                    and not example.expected_claims
                )
                counts["scope_abstention_cases"] += 1
                category = "local_only_cases"
            elif record.execution == "uncertain_abstention":
                from contextbridge.formation.providers.grounded import uncertain_only

                reject_unless(
                    run.metadata.configuration.get("uncertainty_guard") == "no_adopted_choice"
                    and uncertain_only(example.event.model_dump(mode="json"))
                    and prediction.error_code is None
                    and not example.expected_claims
                )
                counts["uncertain_abstention_cases"] += 1
                category = "local_only_cases"
            else:
                reject_unless(
                    record.execution == "local_only"
                    and prediction.error_code is None
                    and all(message.role == "assistant" for message in example.event.messages)
                    and not example.expected_claims
                )
                category = "local_only_cases"
        counts[category] += 1
        output.append(
            {
                "case_id": case_id,
                "category": category,
                "attempted_calls": len(calls) if calls or record is not None else None,
                "execution": record.execution if record else "attempted" if calls else "unknown",
            }
        )
        prior_calls += len(calls)
        for call in calls:
            usage = (call.input_tokens, call.output_tokens)
            prior_tokens += (
                sum(usage)
                if all(value is not None for value in usage)
                else (call.reserved_tokens or 0)
            )
        provider_stopped |= any(call.error_code == "PROVIDER_UNAVAILABLE" for call in calls)
    return {
        "evidence": (
            "validated_case_records"
            if recorded
            else "validated_call_records"
            if sidecar
            else "absent"
        ),
        "provenance": "saved_evidence_not_independently_authenticated",
        "recorded_calls": len(sidecar.calls) if sidecar is not None else None,
        "case_counts": counts,
        "cases": output,
    }
